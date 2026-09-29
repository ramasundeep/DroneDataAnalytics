// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Core/CDSimTypes.h"

#include "CDSimRecorderComponent.generated.h"

class FJsonObject;
class FJsonValue;
struct FCDSimRigidBodyState;

/**
 * Streams session events to the recorder service.
 *
 * Every event is stamped with FCDSimHeader using UCDSimClockSubsystem sim
 * time (THE ordering key) plus wall-clock for reference, buffered, and POSTed
 * in batches to
 *
 *     POST {RecorderUrl}/v1/events      body: {"events": [Event, ...]}
 *
 * Each Event uses the protobuf JSON mapping of cdsim.v1.Event with exactly the
 * camelCase aliases of services/common/src/cdsim_common/events.py:
 *   header{simTimeUs, wallTimeUs, sessionId, actorId, source, seq}, eventId,
 *   relatedEventId, and exactly ONE of stimulus / response / outcome / annotation.
 * Enums are written by name (e.g. "KIND_SYSTEM_FAILURE"); 64-bit ints as
 * strings (canonical proto3 JSON, accepted by the pydantic models).
 *
 * RecorderUrl comes from UCDSimGameInstance (-RecorderUrl=, default the local
 * box). Offline-first: it must point at the LAN/local recorder, never the internet.
 *
 * Telemetry (cdsim.v1.VehicleState) is decimated to 50 Hz and buffered, but
 * its upload path is TODO(Phase 1): the recorder's telemetry ingest endpoint
 * is not defined yet (docs/10_ROADMAP.md). The buffer is bounded and a warning
 * is logged once, so nothing is silently dropped.
 * TODO(Phase 1): durable local spool when the recorder is unreachable.
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIM_API UCDSimRecorderComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCDSimRecorderComponent();

	/** Header.actorId for events from this component (vehicle id, trainee id, "instructor", "system"). */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Recording")
	void SetActorIdForEvents(const FString& InActorId) { ActorId = InActorId; }

	UFUNCTION(BlueprintCallable, Category = "CDSim|Recording")
	FString RecordStimulus(ECDSimStimulusKind Kind, const FString& Code, const FString& Description);

	UFUNCTION(BlueprintCallable, Category = "CDSim|Recording")
	FString RecordResponse(ECDSimResponseKind Kind, const FString& Code, const FString& Description,
		float Magnitude, const FString& RelatedEventId);

	UFUNCTION(BlueprintCallable, Category = "CDSim|Recording")
	FString RecordAnnotation(const FString& Text, const TArray<FString>& Tags);

	/**
	 * Outcome event. DetailField is the proto oneof member name in camelCase:
	 * landingTouchdown, collision, geofenceBreach or procedureStep.
	 */
	FString RecordOutcome(const FString& DetailField, const TSharedRef<FJsonObject>& Detail,
		const FString& RelatedEventId = FString());

	/** Generic event: PayloadField is stimulus / response / outcome / annotation. Returns the eventId. */
	FString RecordEvent(const FString& PayloadField, const TSharedRef<FJsonObject>& Payload,
		const FString& RelatedEventId = FString());

	/** Called by the pawn every physics step; decimated to TelemetryRateHz here. */
	void RecordVehicleState(int64 SimTimeUs, FName PlatformId, const FCDSimRigidBodyState& State,
		const TArray<double>& ActuatorOutputs, const TArray<FName>& ActiveFailures);

	/** Send buffered events now. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Recording")
	void Flush();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** Real seconds between automatic flushes. */
	UPROPERTY(EditAnywhere, Category = "CDSim|Recording")
	float FlushIntervalS = 1.0f;

	/** Flush early once this many events are buffered. */
	UPROPERTY(EditAnywhere, Category = "CDSim|Recording")
	int32 MaxBatchSize = 256;

	/** Hard cap on buffered events (oldest dropped with a warning beyond this). */
	UPROPERTY(EditAnywhere, Category = "CDSim|Recording")
	int32 MaxBufferedEvents = 20000;

	UPROPERTY(EditAnywhere, Category = "CDSim|Recording")
	float TelemetryRateHz = 50.0f;

private:
	FCDSimHeader MakeHeader();
	int64 CurrentSimTimeUs() const;
	void SendBatch(TArray<TSharedPtr<FJsonValue>>&& Batch);
	void Requeue(TArray<TSharedPtr<FJsonValue>>&& Batch);

	FString ActorId = TEXT("system");
	FString SessionId;
	FString RecorderUrl;
	ECDSimSource Source = ECDSimSource::SimClient;
	int64 NextSeq = 0;
	float SecondsSinceFlush = 0.0f;
	int64 NextTelemetryUs = 0;
	bool bWarnedTelemetryUpload = false;

	TArray<TSharedPtr<FJsonValue>> PendingEvents;
	TArray<TSharedPtr<FJsonValue>> PendingTelemetry;
};
