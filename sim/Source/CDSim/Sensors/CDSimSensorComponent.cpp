// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Sensors/CDSimSensorComponent.h"

#include "Core/CDSimFrames.h"
#include "Vehicle/CDSimRigidBody.h"

void UCDSimSensorComponent::ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed)
{
	Spec = InSpec;
	NoiseStream.Initialize(NoiseSeed);
	PeriodUs = Spec.RateHz > 0.0f ? FMath::Max<int64>(1, static_cast<int64>(FMath::RoundToDouble(1.0e6 / Spec.RateHz))) : 0;
	NextSampleUs = 0;
	LastSampleUs = -1;
	SetRelativeLocationAndRotation(CDSimFrames::FrdToUeBodyCm(Spec.MountPositionM),
		CDSimFrames::FrdMountRpyDegToUe(Spec.MountRotationRpyDeg));
}

void UCDSimSensorComponent::TickSensor(int64 SimTimeUs, const FCDSimRigidBodyState& Truth)
{
	if (bDropout || PeriodUs <= 0 || SimTimeUs < NextSampleUs)
	{
		return;
	}
	// Schedule on a fixed grid so the sample times do not drift.
	while (NextSampleUs <= SimTimeUs)
	{
		NextSampleUs += PeriodUs;
	}
	LastSampleUs = SimTimeUs;
	Sample(SimTimeUs, Truth);
}

double UCDSimSensorComponent::Gaussian(double Sigma)
{
	if (Sigma <= 0.0)
	{
		return 0.0;
	}
	// Box-Muller. FRandomStream is deterministic for a given seed.
	const double U1 = FMath::Max(static_cast<double>(NoiseStream.GetFraction()), 1.0e-12);
	const double U2 = static_cast<double>(NoiseStream.GetFraction());
	return Sigma * FMath::Sqrt(-2.0 * FMath::Loge(U1)) * FMath::Cos(2.0 * UE_DOUBLE_PI * U2);
}

FVector UCDSimSensorComponent::GaussianVector(double Sigma)
{
	// Evaluate in a fixed order (X, Y, Z) for determinism.
	const double X = Gaussian(Sigma);
	const double Y = Gaussian(Sigma);
	const double Z = Gaussian(Sigma);
	return FVector(X, Y, Z);
}
