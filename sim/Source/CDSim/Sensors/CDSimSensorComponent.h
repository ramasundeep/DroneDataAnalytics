// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "Math/RandomStream.h"
#include "Vehicle/CDSimPlatformSpec.h"

#include "CDSimSensorComponent.generated.h"

struct FCDSimRigidBodyState;

/**
 * Base class for simulated sensors created from platform.yaml `sensors[]`.
 *
 * Sensors are sampled from the deterministic physics step (not from UE Tick):
 * the owning pawn calls TickSensor() at 400 Hz and the base class gates it to
 * the sensor's rate_hz. Noise uses an FRandomStream seeded from the session and
 * the sensor id, so a replayed session produces identical sensor noise.
 *
 * Mount position/rotation (platform.yaml `mount`, FRD) is applied to the
 * component's relative transform via Core/CDSimFrames.h helpers.
 */
UCLASS(Abstract, ClassGroup = (CDSim))
class CDSIM_API UCDSimSensorComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	/** Apply the spec (rate, mount, noise) and seed the noise stream. */
	virtual void ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed);

	/** Called every physics step with the fresh truth state. Calls Sample() at rate_hz. */
	void TickSensor(int64 SimTimeUs, const FCDSimRigidBodyState& Truth);

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	FName GetSensorId() const { return Spec.Id; }

	/** Sim time of the most recent sample, microseconds. */
	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	int64 GetLastSampleTimeUs() const { return LastSampleUs; }

	/** Failure mode `sensor_dropout`: stop producing samples. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Sensor")
	void SetDropout(bool bInDropout) { bDropout = bInDropout; }

	const FCDSimSensorSpec& GetSpec() const { return Spec; }

protected:
	/** Produce one sample. Implemented by each sensor type. */
	virtual void Sample(int64 SimTimeUs, const FCDSimRigidBodyState& Truth) PURE_VIRTUAL(UCDSimSensorComponent::Sample, );

	/** Zero-mean Gaussian sample with standard deviation Sigma (Box-Muller on the seeded stream). */
	double Gaussian(double Sigma);

	FVector GaussianVector(double Sigma);

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Sensor")
	FCDSimSensorSpec Spec;

	FRandomStream NoiseStream;
	int64 PeriodUs = 0;
	int64 NextSampleUs = 0;
	int64 LastSampleUs = -1;
	bool bDropout = false;
};
