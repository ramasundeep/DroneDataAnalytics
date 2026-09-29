// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Sensors/CDSimImuComponent.h"

#include "Vehicle/CDSimRigidBody.h"

void UCDSimImuComponent::ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed)
{
	Super::ConfigureFromSpec(InSpec, NoiseSeed);
	GyroNoiseRadps = Spec.GetNoise(TEXT("gyro_noise_radps"));
	AccelNoiseMps2 = Spec.GetNoise(TEXT("accel_noise_mps2"));
}

void UCDSimImuComponent::Sample(int64 /*SimTimeUs*/, const FCDSimRigidBodyState& Truth)
{
	GyroFrdRadps = Truth.AngularVelocityFrdRadps + GaussianVector(GyroNoiseRadps);
	AccelFrdMps2 = Truth.SpecificForceFrdMps2 + GaussianVector(AccelNoiseMps2);
}
