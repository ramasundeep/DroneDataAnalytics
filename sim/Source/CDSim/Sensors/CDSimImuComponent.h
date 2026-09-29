// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Sensors/CDSimSensorComponent.h"

#include "CDSimImuComponent.generated.h"

/**
 * IMU (platform.yaml `type: imu`). Noise keys: gyro_noise_radps,
 * accel_noise_mps2 (white Gaussian, 1 sigma per axis).
 *
 * Outputs are in the vehicle body FRD frame. The mount rotation is assumed to
 * be identity (as for imu0); TODO(Phase 1): rotate by the mount and add the
 * lever-arm term for off-CG IMUs. TODO(Phase 3): bias random walk and the
 * `sensor_bias` failure effect (docs/10_ROADMAP.md).
 *
 * The SITL binding receives TRUTH (ArduPilot adds its own sensor noise via
 * SIM_* parameters); these noisy samples feed recording, RL observations and
 * non-autopilot consumers.
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIM_API UCDSimImuComponent : public UCDSimSensorComponent
{
	GENERATED_BODY()

public:
	virtual void ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed) override;

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	FVector GetGyroFrdRadps() const { return GyroFrdRadps; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Sensor")
	FVector GetAccelFrdMps2() const { return AccelFrdMps2; }

protected:
	virtual void Sample(int64 SimTimeUs, const FCDSimRigidBodyState& Truth) override;

private:
	double GyroNoiseRadps = 0.0;
	double AccelNoiseMps2 = 0.0;
	FVector GyroFrdRadps = FVector::ZeroVector;
	FVector AccelFrdMps2 = FVector::ZeroVector;
};
