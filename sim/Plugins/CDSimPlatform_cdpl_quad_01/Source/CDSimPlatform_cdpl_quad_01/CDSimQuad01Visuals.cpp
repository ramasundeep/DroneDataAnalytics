// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "CDSimQuad01Visuals.h"

#include "CDSim.h"
#include "Components/StaticMeshComponent.h"
#include "Core/CDSimFrames.h"
#include "Vehicle/CDSimPlatformSpec.h"

namespace
{
	// Placeholder dimensions, centimetres (UE). Engineering estimates only.
	const FVector BodySizeCm(18.0, 12.0, 6.0);
	const FVector BatterySizeCm(15.0, 7.0, 4.0);
	constexpr double ArmDiameterCm = 2.2;
	constexpr double MotorDiameterCm = 4.0;
	constexpr double MotorHeightCm = 3.0;
	constexpr double PropDiameterCm = 25.4; // 10-inch class
	constexpr double PropThicknessCm = 0.5;
	constexpr double MastDiameterCm = 1.0;
	/** Visual only: degrees of prop rotation per frame at full output. */
	constexpr double VisualSpinDegPerFrameAtFull = 50.0;
} // namespace

void UCDSimQuad01Visuals::BuildVisuals(const FCDSimPlatformSpec& Spec)
{
	// Body and battery (battery strapped on top of the body).
	AddBasicShape(TEXT("Quad01_Body"), ECDSimBasicShape::Cube, FVector::ZeroVector, BodySizeCm);
	const FVector BatteryLocationCm(0.0, 0.0, BodySizeCm.Z * 0.5 + BatterySizeCm.Z * 0.5);
	AddBasicShape(TEXT("Quad01_Battery"), ECDSimBasicShape::Cube, BatteryLocationCm, BatterySizeCm);
	AddPartAnchor(TEXT("SOCKET_Battery"), BatteryLocationCm);

	// Arms, motors, propellers — positions from platform.yaml actuators (FRD metres).
	PropellerMeshes.Reset();
	SpinSigns.Reset();
	for (const FCDSimActuatorSpec& Actuator : Spec.Actuators)
	{
		const FString Suffix = Actuator.Id.ToString().ToUpper(); // m1 -> M1
		const FVector MotorCm = CDSimFrames::FrdToUeBodyCm(Actuator.PositionM);
		const double ArmLengthCm = FVector(MotorCm.X, MotorCm.Y, 0.0).Size();
		const double ArmYawDeg = FMath::RadiansToDegrees(FMath::Atan2(MotorCm.Y, MotorCm.X));

		// Cylinder axis is local Z; pitch 90 lays it flat, yaw points it at the motor.
		AddBasicShape(FName(*FString::Printf(TEXT("Quad01_Arm_%s"), *Suffix)), ECDSimBasicShape::Cylinder,
			FVector(MotorCm.X * 0.5, MotorCm.Y * 0.5, MotorCm.Z), FVector(ArmDiameterCm, ArmDiameterCm, ArmLengthCm),
			FRotator(90.0, ArmYawDeg, 0.0));

		const FVector MotorCentreCm = MotorCm + FVector(0.0, 0.0, MotorHeightCm * 0.5 + ArmDiameterCm * 0.5);
		AddBasicShape(FName(*FString::Printf(TEXT("Quad01_Motor_%s"), *Suffix)), ECDSimBasicShape::Cylinder,
			MotorCentreCm, FVector(MotorDiameterCm, MotorDiameterCm, MotorHeightCm));
		AddPartAnchor(FName(*FString::Printf(TEXT("SOCKET_Motor_%s"), *Suffix)), MotorCentreCm);

		const FVector PropCm = MotorCentreCm + FVector(0.0, 0.0, MotorHeightCm * 0.5 + PropThicknessCm);
		UStaticMeshComponent* Prop = AddBasicShape(FName(*FString::Printf(TEXT("Quad01_Prop_%s"), *Suffix)),
			ECDSimBasicShape::Cylinder, PropCm, FVector(PropDiameterCm, PropDiameterCm, PropThicknessCm));
		AddPartAnchor(FName(*FString::Printf(TEXT("SOCKET_Prop_%s"), *Suffix)), PropCm);
		PropellerMeshes.Add(Prop);
		SpinSigns.Add(Actuator.bCounterClockwise ? 1.0 : -1.0);
	}

	// Parts anchored by offset (e.g. gps_mast) and a check that every socket named in the YAML exists.
	for (const FCDSimMaintenancePartSpec& Part : Spec.MaintenanceParts)
	{
		if (Part.Socket.IsNone())
		{
			const FVector OffsetCm = CDSimFrames::FrdToUeBodyCm(Part.OffsetM);
			const FName AnchorName(*FString::Printf(TEXT("ANCHOR_%s"), *Part.Id.ToString()));
			AddPartAnchor(AnchorName, OffsetCm);
			if (Part.Id == TEXT("gps_mast"))
			{
				AddBasicShape(TEXT("Quad01_GpsMast"), ECDSimBasicShape::Cylinder, OffsetCm * 0.5,
					FVector(MastDiameterCm, MastDiameterCm, FMath::Max(OffsetCm.Z, 1.0)));
				AddBasicShape(TEXT("Quad01_GpsPuck"), ECDSimBasicShape::Cylinder, OffsetCm,
					FVector(5.0, 5.0, 1.5));
			}
		}
		else if (FindPartAnchor(Part.Socket) == nullptr)
		{
			UE_LOG(LogCDSim, Warning, TEXT("cdpl_quad_01 visuals: platform.yaml part '%s' names socket '%s' which the "
										   "placeholder does not provide."),
				*Part.Id.ToString(), *Part.Socket.ToString());
		}
	}

	UE_LOG(LogCDSim, Log, TEXT("cdpl_quad_01: placeholder visuals built (%d meshes, %d anchors)."), PartMeshes.Num(),
		PartAnchors.Num());
}

void UCDSimQuad01Visuals::UpdateActuatorVisuals(const TArray<double>& NormalisedOutputs)
{
	// Frame-rate dependent on purpose: purely cosmetic, never recorded.
	for (int32 Index = 0; Index < PropellerMeshes.Num(); ++Index)
	{
		UStaticMeshComponent* Prop = PropellerMeshes[Index];
		if (Prop == nullptr || !NormalisedOutputs.IsValidIndex(Index))
		{
			continue;
		}
		const double DeltaDeg = SpinSigns[Index] * -VisualSpinDegPerFrameAtFull * NormalisedOutputs[Index];
		Prop->AddLocalRotation(FRotator(0.0, DeltaDeg, 0.0));
	}
}
