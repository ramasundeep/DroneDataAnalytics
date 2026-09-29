// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "UObject/ScriptInterface.h"
#include "Vehicle/CDSimPhysicsBinding.h"
#include "Vehicle/CDSimPlatformSpec.h"
#include "Vehicle/CDSimRigidBody.h"

#include "CDSimVehiclePawn.generated.h"

class UCDSimPlatformVisualsComponent;
class UCDSimRecorderComponent;
class UCDSimSensorComponent;

/**
 * The one generic vehicle pawn. It knows nothing about any specific airframe:
 * everything comes from FCDSimPlatformSpec (platforms/<id>/platform.yaml),
 * and the look comes from the platform plugin's visuals component.
 *
 * Physics: owned here, integrated in C++ by FCDSimRigidBody at the fixed
 * 400 Hz step of UCDSimClockSubsystem — NOT Chaos — so trajectories are
 * deterministic and replayable (see Vehicle/CDSimRigidBody.h for why). The
 * actor transform is only a view of the physics state, updated each frame.
 *
 * Supported classes today: multirotor. TODO(Phase 6+): fixed-wing / VTOL
 * aero models behind the same spec (docs/10_ROADMAP.md).
 *
 * Authority: the server (or standalone instance) integrates physics and talks
 * to SITL. Fleet clients receive the replicated transform.
 * TODO(Phase 5): client-side smoothing of replicated movement.
 */
UCLASS()
class CDSIM_API ACDSimVehiclePawn : public APawn
{
	GENERATED_BODY()

public:
	ACDSimVehiclePawn();

	/**
	 * Select the platform and vehicle id. Call on the server between
	 * SpawnActorDeferred and FinishSpawning (see ACDSimGameMode).
	 */
	void ConfigurePlatform(FName InPlatformId, const FString& InVehicleId);

	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Apply a platform.yaml failure mode by id. Server only. Returns false if unknown. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Vehicle")
	bool ApplyFailureMode(FName FailureId);

	/** Remove all active failure effects. Server only. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Vehicle")
	void ClearFailureModes();

	UFUNCTION(BlueprintPure, Category = "CDSim|Vehicle")
	FName GetPlatformId() const { return PlatformId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Vehicle")
	FString GetVehicleId() const { return VehicleId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Vehicle")
	TArray<FName> GetActiveFailures() const { return ActiveFailures; }

	const FCDSimRigidBodyState& GetPhysicsState() const { return Body.GetState(); }
	const FCDSimPlatformSpec& GetPlatformSpec() const { return Spec; }

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION()
	void OnRep_PlatformId();

	/** Root; the actor transform mirrors the physics state. */
	UPROPERTY(VisibleAnywhere, Category = "CDSim|Vehicle")
	TObjectPtr<USceneComponent> BodyRoot;

	UPROPERTY(VisibleAnywhere, Category = "CDSim|Vehicle")
	TObjectPtr<UCDSimRecorderComponent> Recorder;

	UPROPERTY(VisibleInstanceOnly, Transient, Category = "CDSim|Vehicle")
	TObjectPtr<UCDSimPlatformVisualsComponent> Visuals;

	UPROPERTY(VisibleInstanceOnly, Transient, Category = "CDSim|Vehicle")
	TArray<TObjectPtr<UCDSimSensorComponent>> Sensors;

	UPROPERTY(Transient)
	TScriptInterface<ICDSimPhysicsBinding> PhysicsBinding;

	UPROPERTY(VisibleInstanceOnly, ReplicatedUsing = OnRep_PlatformId, Category = "CDSim|Vehicle")
	FName PlatformId;

	UPROPERTY(VisibleInstanceOnly, Replicated, Category = "CDSim|Vehicle")
	FString VehicleId;

	UPROPERTY(VisibleInstanceOnly, Replicated, Category = "CDSim|Vehicle")
	TArray<FName> ActiveFailures;

private:
	/** Look up the spec in UCDSimPlatformRegistry. Returns false (and logs) if unknown. */
	bool LoadSpec();
	void BuildVisuals();
	void BuildSensors();
	void StartPhysics();
	void StartAutopilotBinding();
	void OnPhysicsStep(int64 SimTimeUs, int64 StepUs);
	void ApplyAutopilotCommands(const TArray<float>& ChannelValues);
	void HandleTouchdown(int64 SimTimeUs);

	FCDSimPlatformSpec Spec;
	FCDSimRigidBody Body;
	FCDSimMultirotorModel Propulsion;

	/** Normalised commands in spec actuator order. */
	TArray<float> ActuatorCommands;
	/** Failure-mode multipliers in spec actuator order. TODO(Phase 3): honour ramp_s. */
	TArray<float> ActuatorScales;

	FDelegateHandle PhysicsStepHandle;
	bool bSpecLoaded = false;
	bool bVisualsBuilt = false;
	bool bWasOnGround = true;
};
