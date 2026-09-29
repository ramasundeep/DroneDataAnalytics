// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"

#include "CDSimClockSubsystem.generated.h"

/** Mirrors cdsim_common.simclock.ClockMode. */
UENUM(BlueprintType)
enum class ECDSimClockMode : uint8
{
	/** Sim time advances with frame time scaled by the sim rate. */
	Realtime,
	/** Sim time advances only when Step() is called (RL lock-step, replay, tests). */
	Stepped,
};

/** Fired once per fixed physics step, AFTER sim time has advanced. Args: new SimTimeUs, StepUs. */
DECLARE_MULTICAST_DELEGATE_TwoParams(FCDSimPhysicsStepDelegate, int64 /*SimTimeUs*/, int64 /*StepUs*/);

/**
 * The authoritative CD Sim clock for a live session.
 *
 * Sim time is an integer count of microseconds, advanced ONLY in whole fixed
 * physics steps of PhysicsStepUs (2500 us = 400 Hz). Everything that must be
 * deterministic (vehicle dynamics, sensors, SITL exchange) subscribes to
 * OnPhysicsStep instead of using UE's variable frame DeltaTime.
 *
 * Semantics mirror services/common/src/cdsim_common/simclock.py:
 *   - starts paused at SimTimeUs == 0;
 *   - rate is clamped to [0.1, 10];
 *   - Realtime: frame DeltaTime * rate is accumulated and drained in whole
 *     physics steps (rate changes never make time jump or run backwards);
 *   - Stepped: only Step(Ticks) advances time.
 * One deliberate difference: the Python clock rejects out-of-range rates with
 * ValueError; this in-engine clock clamps and logs a warning, because a UI
 * slider must never crash a session.
 *
 * Only the server / standalone instance owns the clock. Fleet clients read the
 * replicated value from ACDSimFleetGameState. TODO(Phase 5): client-side
 * interpolation of replicated sim time (docs/10_ROADMAP.md).
 */
UCLASS()
class CDSIM_API UCDSimClockSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	static constexpr int64 PhysicsStepUs = 2500;
	static constexpr float MinRate = 0.1f;
	static constexpr float MaxRate = 10.0f;
	/** Guard against a "spiral of death" after a long hitch: at most this many steps per frame. */
	static constexpr int32 MaxStepsPerFrame = 400;

	// USubsystem
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// FTickableGameObject (via UTickableWorldSubsystem)
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** Start or resume advancing sim time. Idempotent. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Clock")
	void Resume();

	/** Freeze sim time. Idempotent. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Clock")
	void Pause();

	UFUNCTION(BlueprintPure, Category = "CDSim|Clock")
	bool IsRunning() const { return bRunning; }

	/** Set the real-time multiplier, clamped to [MinRate, MaxRate]. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Clock")
	void SetSimRate(float NewRate);

	UFUNCTION(BlueprintPure, Category = "CDSim|Clock")
	float GetSimRate() const { return SimRate; }

	UFUNCTION(BlueprintCallable, Category = "CDSim|Clock")
	void SetMode(ECDSimClockMode NewMode);

	UFUNCTION(BlueprintPure, Category = "CDSim|Clock")
	ECDSimClockMode GetMode() const { return Mode; }

	/**
	 * Advance a Stepped clock by Ticks physics steps, firing OnPhysicsStep for
	 * each. Returns the new sim time. Ignored (with a warning) in Realtime mode.
	 */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Clock")
	int64 Step(int32 Ticks = 1);

	/** Current sim time in integer microseconds since session start. */
	UFUNCTION(BlueprintPure, Category = "CDSim|Clock")
	int64 GetSimTimeUs() const { return SimTimeUs; }

	/** Number of physics steps taken so far (SimTimeUs / PhysicsStepUs). */
	int64 GetStepCount() const { return StepCount; }

	/** Subscribe here to run code at exactly 400 Hz of sim time. */
	FCDSimPhysicsStepDelegate OnPhysicsStep;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	void AdvanceOneStep();

	int64 SimTimeUs = 0;
	int64 StepCount = 0;
	/** Real-time remainder not yet drained into whole steps, in microseconds of sim time. */
	double AccumulatorUs = 0.0;
	float SimRate = 1.0f;
	ECDSimClockMode Mode = ECDSimClockMode::Realtime;
	bool bRunning = false;
};
