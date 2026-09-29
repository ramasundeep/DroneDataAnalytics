// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Vehicle/CDSimVehiclePawn.h"

#include "CDSim.h"
#include "Components/SceneComponent.h"
#include "Core/CDSimClockSubsystem.h"
#include "Core/CDSimFrames.h"
#include "Core/CDSimGameInstance.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "Recording/CDSimRecorderComponent.h"
#include "Sensors/CDSimDownCameraComponent.h"
#include "Sensors/CDSimGpsComponent.h"
#include "Sensors/CDSimImuComponent.h"
#include "Vehicle/ArduPilotJsonBinding.h"
#include "Vehicle/CDSimPlatformRegistry.h"
#include "Vehicle/CDSimPlatformVisualsComponent.h"
#include "World/CDSimAreaLoader.h"

ACDSimVehiclePawn::ACDSimVehiclePawn()
{
	PrimaryActorTick.bCanEverTick = true;
	bReplicates = true;
	SetReplicateMovement(true);

	BodyRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BodyRoot"));
	SetRootComponent(BodyRoot);

	Recorder = CreateDefaultSubobject<UCDSimRecorderComponent>(TEXT("Recorder"));
}

void ACDSimVehiclePawn::ConfigurePlatform(FName InPlatformId, const FString& InVehicleId)
{
	PlatformId = InPlatformId;
	VehicleId = InVehicleId;
}

void ACDSimVehiclePawn::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ACDSimVehiclePawn, PlatformId);
	DOREPLIFETIME(ACDSimVehiclePawn, VehicleId);
	DOREPLIFETIME(ACDSimVehiclePawn, ActiveFailures);
}

bool ACDSimVehiclePawn::LoadSpec()
{
	if (bSpecLoaded)
	{
		return true;
	}
	const UGameInstance* GameInstance = GetGameInstance();
	const UCDSimPlatformRegistry* Registry =
		GameInstance != nullptr ? GameInstance->GetSubsystem<UCDSimPlatformRegistry>() : nullptr;
	const FCDSimPlatformSpec* Found = Registry != nullptr ? Registry->FindPlatform(PlatformId) : nullptr;
	if (Found == nullptr)
	{
		UE_LOG(LogCDSim, Error, TEXT("Vehicle '%s': unknown platform '%s'. Is sim/Config/Platforms/%s.json exported?"),
			*VehicleId, *PlatformId.ToString(), *PlatformId.ToString());
		return false;
	}
	Spec = *Found;
	bSpecLoaded = true;
	return true;
}

void ACDSimVehiclePawn::BeginPlay()
{
	Super::BeginPlay();

	if (PlatformId.IsNone() || !LoadSpec())
	{
		return; // Clients may get PlatformId later via OnRep_PlatformId.
	}
	BuildVisuals();

	if (HasAuthority())
	{
		if (Recorder != nullptr)
		{
			Recorder->SetActorIdForEvents(VehicleId);
		}
		BuildSensors();
		StartPhysics();
		StartAutopilotBinding();
	}
}

void ACDSimVehiclePawn::OnRep_PlatformId()
{
	if (!PlatformId.IsNone() && LoadSpec())
	{
		BuildVisuals();
	}
}

void ACDSimVehiclePawn::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (UCDSimClockSubsystem* Clock = World->GetSubsystem<UCDSimClockSubsystem>())
		{
			Clock->OnPhysicsStep.Remove(PhysicsStepHandle);
		}
	}
	PhysicsStepHandle.Reset();
	if (PhysicsBinding.GetInterface() != nullptr)
	{
		PhysicsBinding->StopBinding();
	}
	PhysicsBinding = nullptr;
	Super::EndPlay(EndPlayReason);
}

void ACDSimVehiclePawn::BuildVisuals()
{
	if (bVisualsBuilt || IsRunningDedicatedServer())
	{
		return;
	}
	UClass* VisualsClass = FCDSimPlatformVisualsRegistry::ResolveVisualsClass(PlatformId);
	Visuals = NewObject<UCDSimPlatformVisualsComponent>(this, VisualsClass, TEXT("PlatformVisuals"));
	Visuals->SetupAttachment(BodyRoot);
	Visuals->RegisterComponent();
	AddInstanceComponent(Visuals);
	Visuals->BuildVisuals(Spec);
	bVisualsBuilt = true;
}

void ACDSimVehiclePawn::BuildSensors()
{
	const UCDSimGameInstance* GameInstance = Cast<UCDSimGameInstance>(GetGameInstance());
	const FString SessionId = GameInstance != nullptr ? GameInstance->GetSessionId() : FString();
	const UCDSimAreaLoader* Area = GetWorld()->GetSubsystem<UCDSimAreaLoader>();

	for (const FCDSimSensorSpec& SensorSpec : Spec.Sensors)
	{
		UClass* SensorClass = nullptr;
		if (SensorSpec.Type == TEXT("imu"))
		{
			SensorClass = UCDSimImuComponent::StaticClass();
		}
		else if (SensorSpec.Type == TEXT("gps"))
		{
			SensorClass = UCDSimGpsComponent::StaticClass();
		}
		else if (SensorSpec.Type == TEXT("camera"))
		{
			SensorClass = UCDSimDownCameraComponent::StaticClass();
		}
		else
		{
			// TODO(Phase 1): baro, mag, rangefinder components (docs/10_ROADMAP.md).
			UE_LOG(LogCDSim, Log, TEXT("Vehicle '%s': sensor '%s' type '%s' not simulated in-engine yet."), *VehicleId,
				*SensorSpec.Id.ToString(), *SensorSpec.Type);
			continue;
		}

		UCDSimSensorComponent* Sensor = NewObject<UCDSimSensorComponent>(this, SensorClass, SensorSpec.Id);
		Sensor->SetupAttachment(BodyRoot);
		Sensor->RegisterComponent();
		AddInstanceComponent(Sensor);

		// Seed from strings only (FName hashes are not stable across runs).
		const int32 Seed = static_cast<int32>(HashCombine(GetTypeHash(SessionId), GetTypeHash(SensorSpec.Id.ToString())));
		Sensor->ConfigureFromSpec(SensorSpec, Seed);

		if (UCDSimGpsComponent* Gps = Cast<UCDSimGpsComponent>(Sensor))
		{
			if (Area != nullptr)
			{
				Gps->SetGeoOrigin(Area->GetGeoOrigin());
			}
		}
		Sensors.Add(Sensor);
	}
}

void ACDSimVehiclePawn::StartPhysics()
{
	if (Spec.Class != TEXT("multirotor"))
	{
		UE_LOG(LogCDSim, Error,
			TEXT("Vehicle '%s': platform class '%s' has no dynamics model yet (multirotor only). "
				 "TODO(Phase 6+): fixed-wing / VTOL."),
			*VehicleId, *Spec.Class);
		return;
	}

	Body.Configure(Spec);
	Propulsion.Configure(Spec);
	ActuatorCommands.Init(0.0f, Spec.Actuators.Num());
	ActuatorScales.Init(1.0f, Spec.Actuators.Num());

	FCDSimRigidBodyState Initial;
	Initial.PositionNedM = CDSimFrames::UeCmToNed(GetActorLocation());
	Initial.AttitudeFrdToNed = CDSimFrames::UeQuatToNed(GetActorQuat());
	if (const UCDSimAreaLoader* Area = GetWorld()->GetSubsystem<UCDSimAreaLoader>())
	{
		Body.SetGroundDownM(Area->GetGroundDownM(Initial.PositionNedM));
		Initial.PositionNedM.Z = FMath::Min(Initial.PositionNedM.Z, Area->GetGroundDownM(Initial.PositionNedM));
	}
	Body.Reset(Initial);
	bWasOnGround = true;

	if (UCDSimClockSubsystem* Clock = GetWorld()->GetSubsystem<UCDSimClockSubsystem>())
	{
		PhysicsStepHandle = Clock->OnPhysicsStep.AddUObject(this, &ACDSimVehiclePawn::OnPhysicsStep);
	}
	else
	{
		UE_LOG(LogCDSim, Error, TEXT("Vehicle '%s': no sim clock in this world; physics will not run."), *VehicleId);
	}
}

void ACDSimVehiclePawn::StartAutopilotBinding()
{
	const UCDSimGameInstance* GameInstance = Cast<UCDSimGameInstance>(GetGameInstance());
	if (GameInstance != nullptr && !GameInstance->IsSitlEnabled())
	{
		return;
	}
	if (Spec.AutopilotType != TEXT("ardupilot"))
	{
		// TODO(Phase 1+): PX4 binding implementing ICDSimPhysicsBinding (docs/ADR/0003).
		UE_LOG(LogCDSim, Warning, TEXT("Vehicle '%s': autopilot type '%s' has no binding yet."), *VehicleId,
			*Spec.AutopilotType);
		return;
	}
	UArduPilotJsonBinding* Binding = NewObject<UArduPilotJsonBinding>(this);
	// Fleet mode: one SITL per vehicle on consecutive ports is TODO(Phase 5).
	Binding->SetListenPort(GameInstance != nullptr ? GameInstance->GetSitlPort() : UArduPilotJsonBinding::DefaultPort);
	if (Binding->StartBinding())
	{
		PhysicsBinding = Binding;
	}
}

void ACDSimVehiclePawn::ApplyAutopilotCommands(const TArray<float>& ChannelValues)
{
	for (int32 Index = 0; Index < Spec.Actuators.Num(); ++Index)
	{
		const int32 Channel = Spec.Actuators[Index].OutputChannel - 1; // platform.yaml channels are 1-based
		if (ChannelValues.IsValidIndex(Channel))
		{
			ActuatorCommands[Index] = ChannelValues[Channel];
		}
	}
}

void ACDSimVehiclePawn::OnPhysicsStep(int64 SimTimeUs, int64 StepUs)
{
	const double DtS = static_cast<double>(StepUs) * 1.0e-6;

	// 1. Autopilot outputs (hold last if nothing new).
	if (PhysicsBinding.GetInterface() != nullptr)
	{
		TArray<float> Channels;
		if (PhysicsBinding->ReceiveActuatorCommands(Channels))
		{
			ApplyAutopilotCommands(Channels);
		}
	}

	// 2. Dynamics.
	const FCDSimForceTorque Actuation = Propulsion.Step(ActuatorCommands, ActuatorScales, DtS);
	Body.Step(Actuation, DtS);
	const FCDSimRigidBodyState& State = Body.GetState();

	// 3. Sensors.
	for (UCDSimSensorComponent* Sensor : Sensors)
	{
		if (Sensor != nullptr)
		{
			Sensor->TickSensor(SimTimeUs, State);
		}
	}

	// 4. Reply to the autopilot with truth (ArduPilot adds its own sensor noise).
	if (PhysicsBinding.GetInterface() != nullptr)
	{
		FCDSimAutopilotSensorState Out;
		Out.TimestampS = static_cast<double>(SimTimeUs) * 1.0e-6;
		Out.GyroFrdRadps = State.AngularVelocityFrdRadps;
		Out.AccelFrdMps2 = State.SpecificForceFrdMps2;
		Out.PositionNedM = State.PositionNedM;
		Out.AttitudeRpyRad = CDSimFrames::QuatToEulerRpyRad(State.AttitudeFrdToNed);
		Out.VelocityNedMps = State.VelocityNedMps;
		PhysicsBinding->SendSensorState(Out);
	}

	// 5. Recording (decimated inside the recorder) and touchdown detection.
	if (Recorder != nullptr)
	{
		Recorder->RecordVehicleState(SimTimeUs, PlatformId, State, Propulsion.GetMotorOutputs(), ActiveFailures);
	}
	if (State.bOnGround && !bWasOnGround)
	{
		HandleTouchdown(SimTimeUs);
	}
	bWasOnGround = State.bOnGround;
}

void ACDSimVehiclePawn::HandleTouchdown(int64 /*SimTimeUs*/)
{
	const UCDSimAreaLoader* Area = GetWorld()->GetSubsystem<UCDSimAreaLoader>();
	if (Area == nullptr || Recorder == nullptr)
	{
		return;
	}
	const FVector Position = Body.GetState().PositionNedM;
	FName NearestPad;
	double NearestDistance = TNumericLimits<double>::Max();
	for (const FCDSimLandingPadSpec& Pad : Area->GetAreaSpec().LandingPads)
	{
		FVector PadNed;
		if (Area->GetPadPositionNed(Pad.Id, PadNed))
		{
			const double Distance = FVector::Dist2D(Position, PadNed);
			if (Distance < NearestDistance)
			{
				NearestDistance = Distance;
				NearestPad = Pad.Id;
			}
		}
	}
	if (NearestPad.IsNone())
	{
		return;
	}
	// cdsim.v1.LandingTouchdown (proto-JSON camelCase, see cdsim_common.events.LandingTouchdown).
	TSharedRef<FJsonObject> Touchdown = MakeShared<FJsonObject>();
	Touchdown->SetStringField(TEXT("padId"), NearestPad.ToString());
	Touchdown->SetNumberField(TEXT("radialErrorM"), NearestDistance);
	TSharedRef<FJsonObject> Velocity = MakeShared<FJsonObject>();
	Velocity->SetNumberField(TEXT("x"), 0.0);
	Velocity->SetNumberField(TEXT("y"), 0.0);
	Velocity->SetNumberField(TEXT("z"), Body.GetLastImpactSpeedMps());
	Touchdown->SetObjectField(TEXT("velocityMps"), Velocity);
	Recorder->RecordOutcome(TEXT("landingTouchdown"), Touchdown);
}

void ACDSimVehiclePawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (HasAuthority() && bSpecLoaded)
	{
		const FCDSimRigidBodyState& State = Body.GetState();
		SetActorLocationAndRotation(CDSimFrames::NedToUeCm(State.PositionNedM),
			CDSimFrames::NedQuatToUe(State.AttitudeFrdToNed), false, nullptr, ETeleportType::TeleportPhysics);
	}
	if (Visuals != nullptr)
	{
		Visuals->UpdateActuatorVisuals(Propulsion.GetMotorOutputs());
	}
}

bool ACDSimVehiclePawn::ApplyFailureMode(FName FailureId)
{
	if (!HasAuthority())
	{
		return false;
	}
	const FCDSimFailureModeSpec* Failure = Spec.FindFailureMode(FailureId);
	if (Failure == nullptr)
	{
		UE_LOG(LogCDSim, Warning, TEXT("Vehicle '%s': unknown failure mode '%s'."), *VehicleId, *FailureId.ToString());
		return false;
	}

	bool bApplied = false;
	if (Failure->EffectType == TEXT("actuator_scale"))
	{
		const int32 Index = Spec.Actuators.IndexOfByPredicate(
			[Failure](const FCDSimActuatorSpec& A) { return A.Id == Failure->EffectTarget; });
		if (ActuatorScales.IsValidIndex(Index))
		{
			ActuatorScales[Index] = Failure->EffectValue; // TODO(Phase 3): ramp over EffectRampS.
			bApplied = true;
		}
	}
	else if (Failure->EffectType == TEXT("sensor_dropout"))
	{
		for (UCDSimSensorComponent* Sensor : Sensors)
		{
			if (Sensor != nullptr && Sensor->GetSensorId() == Failure->EffectTarget)
			{
				Sensor->SetDropout(true);
				bApplied = true;
			}
		}
		// TODO(Phase 3): also drive ArduPilot SIM_GPS_DISABLE etc. over MAVLink for autopilot-visible dropouts.
	}
	else
	{
		// sensor_bias, battery_sag, comms_loss: TODO(Phase 3) (docs/10_ROADMAP.md).
		UE_LOG(LogCDSim, Warning, TEXT("Vehicle '%s': failure effect '%s' not implemented yet (Phase 3)."), *VehicleId,
			*Failure->EffectType);
	}

	if (bApplied)
	{
		ActiveFailures.AddUnique(FailureId);
		if (Recorder != nullptr)
		{
			Recorder->RecordStimulus(ECDSimStimulusKind::SystemFailure, FailureId.ToString(), Failure->Name);
		}
	}
	return bApplied;
}

void ACDSimVehiclePawn::ClearFailureModes()
{
	if (!HasAuthority())
	{
		return;
	}
	for (float& Scale : ActuatorScales)
	{
		Scale = 1.0f;
	}
	for (UCDSimSensorComponent* Sensor : Sensors)
	{
		if (Sensor != nullptr)
		{
			Sensor->SetDropout(false);
		}
	}
	ActiveFailures.Reset();
}
