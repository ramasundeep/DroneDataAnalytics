// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Sensors/CDSimGpsComponent.h"

#include "Vehicle/CDSimRigidBody.h"

void UCDSimGpsComponent::ConfigureFromSpec(const FCDSimSensorSpec& InSpec, int32 NoiseSeed)
{
	Super::ConfigureFromSpec(InSpec, NoiseSeed);
	HorizontalSigmaM = Spec.GetNoise(TEXT("horizontal_m"));
	VerticalSigmaM = Spec.GetNoise(TEXT("vertical_m"));
}

void UCDSimGpsComponent::Sample(int64 /*SimTimeUs*/, const FCDSimRigidBodyState& Truth)
{
	// Antenna lever arm: mount position (FRD) rotated into NED.
	const FVector AntennaNed = Truth.PositionNedM + Truth.AttitudeFrdToNed.RotateVector(Spec.MountPositionM);
	const double NoiseN = Gaussian(HorizontalSigmaM);
	const double NoiseE = Gaussian(HorizontalSigmaM);
	const double NoiseD = Gaussian(VerticalSigmaM);
	Origin.NedToGeo(AntennaNed + FVector(NoiseN, NoiseE, NoiseD), LatDeg, LonDeg, AltMslM);
	VelocityNedMps = Truth.VelocityNedMps;
}
