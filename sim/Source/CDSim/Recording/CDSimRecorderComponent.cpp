// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Recording/CDSimRecorderComponent.h"

#include "CDSim.h"
#include "Core/CDSimClockSubsystem.h"
#include "Core/CDSimFrames.h"
#include "Core/CDSimGameInstance.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Vehicle/CDSimRigidBody.h"

namespace
{
	TSharedRef<FJsonObject> Vec3Json(const FVector& V)
	{
		TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
		Json->SetNumberField(TEXT("x"), V.X);
		Json->SetNumberField(TEXT("y"), V.Y);
		Json->SetNumberField(TEXT("z"), V.Z);
		return Json;
	}
} // namespace

UCDSimRecorderComponent::UCDSimRecorderComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	// Keep flushing while the game is paused so nothing sits in memory.
	PrimaryComponentTick.bTickEvenWhenPaused = true;
}

void UCDSimRecorderComponent::BeginPlay()
{
	Super::BeginPlay();
	if (const UCDSimGameInstance* GameInstance = Cast<UCDSimGameInstance>(GetWorld()->GetGameInstance()))
	{
		SessionId = GameInstance->GetSessionId();
		RecorderUrl = GameInstance->GetRecorderUrl();
	}
	RecorderUrl.RemoveFromEnd(TEXT("/"));
	Source = GetNetMode() == NM_DedicatedServer ? ECDSimSource::SimServer : ECDSimSource::SimClient;
}

void UCDSimRecorderComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	Flush();
	Super::EndPlay(EndPlayReason);
}

int64 UCDSimRecorderComponent::CurrentSimTimeUs() const
{
	const UWorld* World = GetWorld();
	const UCDSimClockSubsystem* Clock = World != nullptr ? World->GetSubsystem<UCDSimClockSubsystem>() : nullptr;
	return Clock != nullptr ? Clock->GetSimTimeUs() : 0;
}

FCDSimHeader UCDSimRecorderComponent::MakeHeader()
{
	FCDSimHeader Header;
	Header.SimTimeUs = CurrentSimTimeUs();
	Header.WallTimeUs = CDSimTypes::WallTimeNowUs();
	Header.SessionId = SessionId;
	Header.ActorId = ActorId;
	Header.Source = Source;
	Header.Seq = NextSeq++;
	return Header;
}

FString UCDSimRecorderComponent::RecordEvent(
	const FString& PayloadField, const TSharedRef<FJsonObject>& Payload, const FString& RelatedEventId)
{
	const FString EventId = CDSimTypes::NewUuidString();

	TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
	Event->SetObjectField(TEXT("header"), MakeHeader().ToProtoJson());
	Event->SetStringField(TEXT("eventId"), EventId);
	if (!RelatedEventId.IsEmpty())
	{
		Event->SetStringField(TEXT("relatedEventId"), RelatedEventId);
	}
	Event->SetObjectField(PayloadField, Payload);

	if (PendingEvents.Num() >= MaxBufferedEvents)
	{
		UE_LOG(LogCDSim, Warning, TEXT("Recorder: buffer full (%d); dropping oldest event."), MaxBufferedEvents);
		PendingEvents.RemoveAt(0);
	}
	PendingEvents.Add(MakeShared<FJsonValueObject>(Event));
	if (PendingEvents.Num() >= MaxBatchSize)
	{
		Flush();
	}
	return EventId;
}

FString UCDSimRecorderComponent::RecordStimulus(ECDSimStimulusKind Kind, const FString& Code, const FString& Description)
{
	TSharedRef<FJsonObject> Stimulus = MakeShared<FJsonObject>();
	Stimulus->SetStringField(TEXT("kind"), CDSimTypes::StimulusKindToProtoName(Kind));
	Stimulus->SetStringField(TEXT("code"), Code);
	Stimulus->SetStringField(TEXT("description"), Description);
	return RecordEvent(TEXT("stimulus"), Stimulus);
}

FString UCDSimRecorderComponent::RecordResponse(ECDSimResponseKind Kind, const FString& Code,
	const FString& Description, float Magnitude, const FString& RelatedEventId)
{
	TSharedRef<FJsonObject> Response = MakeShared<FJsonObject>();
	Response->SetStringField(TEXT("kind"), CDSimTypes::ResponseKindToProtoName(Kind));
	Response->SetStringField(TEXT("code"), Code);
	Response->SetStringField(TEXT("description"), Description);
	Response->SetNumberField(TEXT("magnitude"), Magnitude);
	return RecordEvent(TEXT("response"), Response, RelatedEventId);
}

FString UCDSimRecorderComponent::RecordAnnotation(const FString& Text, const TArray<FString>& Tags)
{
	TSharedRef<FJsonObject> Annotation = MakeShared<FJsonObject>();
	Annotation->SetStringField(TEXT("text"), Text);
	TArray<TSharedPtr<FJsonValue>> TagValues;
	for (const FString& Tag : Tags)
	{
		TagValues.Add(MakeShared<FJsonValueString>(Tag));
	}
	Annotation->SetArrayField(TEXT("tags"), TagValues);
	return RecordEvent(TEXT("annotation"), Annotation);
}

FString UCDSimRecorderComponent::RecordOutcome(
	const FString& DetailField, const TSharedRef<FJsonObject>& Detail, const FString& RelatedEventId)
{
	TSharedRef<FJsonObject> Outcome = MakeShared<FJsonObject>();
	Outcome->SetObjectField(DetailField, Detail);
	return RecordEvent(TEXT("outcome"), Outcome, RelatedEventId);
}

void UCDSimRecorderComponent::RecordVehicleState(int64 SimTimeUs, FName PlatformId, const FCDSimRigidBodyState& State,
	const TArray<double>& ActuatorOutputs, const TArray<FName>& ActiveFailures)
{
	if (TelemetryRateHz <= 0.0f || SimTimeUs < NextTelemetryUs)
	{
		return;
	}
	NextTelemetryUs = SimTimeUs + static_cast<int64>(1.0e6 / TelemetryRateHz);

	// cdsim.v1.VehicleState (schemas/telemetry.proto), proto-JSON camelCase.
	// The proto wants ENU velocity and body->ENU attitude; physics is NED/FRD.
	TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetObjectField(TEXT("header"), MakeHeader().ToProtoJson());
	Json->SetStringField(TEXT("vehicleId"), ActorId);
	Json->SetStringField(TEXT("platformId"), PlatformId.ToString());
	const FVector& P = State.PositionNedM;
	Json->SetObjectField(TEXT("positionLocalM"), Vec3Json(FVector(P.Y, P.X, -P.Z))); // NED -> ENU
	const FVector& V = State.VelocityNedMps;
	Json->SetObjectField(TEXT("velocityEnuMps"), Vec3Json(FVector(V.Y, V.X, -V.Z)));
	Json->SetObjectField(TEXT("angularVelocityRadps"), Vec3Json(State.AngularVelocityFrdRadps));
	Json->SetObjectField(TEXT("accelBodyMps2"), Vec3Json(State.SpecificForceFrdMps2));
	TArray<TSharedPtr<FJsonValue>> Outputs;
	for (const double Output : ActuatorOutputs)
	{
		Outputs.Add(MakeShared<FJsonValueNumber>(Output));
	}
	Json->SetArrayField(TEXT("actuatorOutputs"), Outputs);
	TArray<TSharedPtr<FJsonValue>> Failures;
	for (const FName& Failure : ActiveFailures)
	{
		Failures.Add(MakeShared<FJsonValueString>(Failure.ToString()));
	}
	Json->SetArrayField(TEXT("activeFailures"), Failures);
	// TODO(Phase 1): position (GeoPoint), attitude (Quat, body->ENU), altitudeAglM, flightMode, armed, battery.

	if (PendingTelemetry.Num() >= MaxBufferedEvents)
	{
		PendingTelemetry.RemoveAt(0);
	}
	PendingTelemetry.Add(MakeShared<FJsonValueObject>(Json));
}

void UCDSimRecorderComponent::TickComponent(
	float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	SecondsSinceFlush += DeltaTime;
	if (SecondsSinceFlush >= FlushIntervalS)
	{
		Flush();
	}
}

void UCDSimRecorderComponent::Flush()
{
	SecondsSinceFlush = 0.0f;

	if (PendingTelemetry.Num() > 0 && !bWarnedTelemetryUpload)
	{
		bWarnedTelemetryUpload = true;
		UE_LOG(LogCDSim, Warning,
			TEXT("Recorder: telemetry upload is not implemented yet (TODO(Phase 1)); keeping the last %d "
				 "VehicleState samples in memory only."),
			MaxBufferedEvents);
	}

	if (PendingEvents.Num() == 0)
	{
		return;
	}
	if (RecorderUrl.IsEmpty() || SessionId.IsEmpty())
	{
		UE_LOG(LogCDSim, Warning, TEXT("Recorder: no RecorderUrl/SessionId; holding %d events."), PendingEvents.Num());
		return;
	}
	TArray<TSharedPtr<FJsonValue>> Batch = MoveTemp(PendingEvents);
	PendingEvents.Reset();
	SendBatch(MoveTemp(Batch));
}

void UCDSimRecorderComponent::SendBatch(TArray<TSharedPtr<FJsonValue>>&& Batch)
{
	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetArrayField(TEXT("events"), Batch);
	FString BodyText;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&BodyText);
	FJsonSerializer::Serialize(Body, Writer);

	const TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	Request->SetURL(RecorderUrl + TEXT("/v1/events"));
	Request->SetVerb(TEXT("POST"));
	Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Request->SetContentAsString(BodyText);

	const int32 Count = Batch.Num();
	Request->OnProcessRequestComplete().BindWeakLambda(this,
		[this, Batch = MoveTemp(Batch), Count](FHttpRequestPtr /*Req*/, FHttpResponsePtr Response, bool bSucceeded) mutable
		{
			const int32 Code = Response.IsValid() ? Response->GetResponseCode() : 0;
			if (bSucceeded && Code >= 200 && Code < 300)
			{
				UE_LOG(LogCDSim, Verbose, TEXT("Recorder: sent %d events."), Count);
				return;
			}
			UE_LOG(LogCDSim, Warning, TEXT("Recorder: POST /v1/events failed (HTTP %d); re-queueing %d events."), Code,
				Count);
			Requeue(MoveTemp(Batch));
		});
	Request->ProcessRequest();
}

void UCDSimRecorderComponent::Requeue(TArray<TSharedPtr<FJsonValue>>&& Batch)
{
	// Failed batch goes back in front, preserving order; the recorder sorts by
	// (simTimeUs, seq) anyway (cdsim_common.events.Event.sort_key).
	Batch.Append(MoveTemp(PendingEvents));
	PendingEvents = MoveTemp(Batch);
	if (PendingEvents.Num() > MaxBufferedEvents)
	{
		const int32 Excess = PendingEvents.Num() - MaxBufferedEvents;
		UE_LOG(LogCDSim, Warning, TEXT("Recorder: buffer over cap; dropping %d oldest events."), Excess);
		PendingEvents.RemoveAt(0, Excess);
	}
}
