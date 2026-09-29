// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Vehicle/CDSimPlatformSpec.h"

#include "Core/CDSimJson.h"

double FCDSimActuatorSpec::EvaluateCurve(const TArray<FVector2D>& ThrustCurve, double Command)
{
	const double C = FMath::Clamp(Command, 0.0, 1.0);
	if (ThrustCurve.Num() < 2)
	{
		return C;
	}
	if (C <= ThrustCurve[0].X)
	{
		return ThrustCurve[0].Y;
	}
	for (int32 Index = 1; Index < ThrustCurve.Num(); ++Index)
	{
		const FVector2D& A = ThrustCurve[Index - 1];
		const FVector2D& B = ThrustCurve[Index];
		if (C <= B.X)
		{
			const double Span = B.X - A.X;
			const double Alpha = Span > UE_SMALL_NUMBER ? (C - A.X) / Span : 1.0;
			return FMath::Lerp(A.Y, B.Y, Alpha);
		}
	}
	return ThrustCurve.Last().Y;
}

float FCDSimSensorSpec::GetNoise(FName Key, float Default) const
{
	const float* Value = Noise.Find(Key);
	return Value != nullptr ? *Value : Default;
}

float FCDSimSensorSpec::GetParam(FName Key, float Default) const
{
	const float* Value = Params.Find(Key);
	return Value != nullptr ? *Value : Default;
}

const FCDSimActuatorSpec* FCDSimPlatformSpec::FindActuator(FName ActuatorId) const
{
	return Actuators.FindByPredicate([ActuatorId](const FCDSimActuatorSpec& A) { return A.Id == ActuatorId; });
}

const FCDSimFailureModeSpec* FCDSimPlatformSpec::FindFailureMode(FName FailureId) const
{
	return FailureModes.FindByPredicate([FailureId](const FCDSimFailureModeSpec& F) { return F.Id == FailureId; });
}

bool FCDSimPlatformSpec::FromJson(const TSharedPtr<FJsonObject>& Root, FCDSimPlatformSpec& OutSpec, FString& OutError)
{
	using namespace CDSimJson;

	if (!Root.IsValid())
	{
		OutError = TEXT("platform JSON is not an object");
		return false;
	}
	OutSpec = FCDSimPlatformSpec();

	const TSharedPtr<FJsonObject> Identity = Object(Root, TEXT("identity"));
	OutSpec.Id = FName(*String(Identity, TEXT("id")));
	if (OutSpec.Id.IsNone())
	{
		OutError = TEXT("platform JSON has no identity.id");
		return false;
	}
	OutSpec.Name = String(Identity, TEXT("name"));
	OutSpec.Version = String(Identity, TEXT("version"));
	OutSpec.Status = String(Identity, TEXT("status"));
	OutSpec.Class = String(Root, TEXT("class"));

	const TSharedPtr<FJsonObject> Mass = Object(Root, TEXT("mass_properties"));
	OutSpec.MassKg = static_cast<float>(Number(Mass, TEXT("mass_kg")));
	OutSpec.CgM = Vector3(Mass, TEXT("cg_m"));
	const TSharedPtr<FJsonObject> Inertia = Object(Mass, TEXT("inertia_kgm2"));
	OutSpec.InertiaKgm2 =
		FVector(Number(Inertia, TEXT("ixx"), 1.0), Number(Inertia, TEXT("iyy"), 1.0), Number(Inertia, TEXT("izz"), 1.0));
	if (OutSpec.MassKg <= 0.0f)
	{
		OutError = TEXT("mass_properties.mass_kg must be > 0");
		return false;
	}

	const TSharedPtr<FJsonObject> Aero = Object(Root, TEXT("aero"));
	OutSpec.LinearDragFrd = Vector3(Aero, TEXT("drag_coefficients"));

	const TSharedPtr<FJsonObject> Propulsion = Object(Root, TEXT("propulsion"));
	if (const TArray<TSharedPtr<FJsonValue>>* Actuators = Array(Propulsion, TEXT("actuators")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Actuators)
		{
			const TSharedPtr<FJsonObject> A = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!A.IsValid())
			{
				continue;
			}
			FCDSimActuatorSpec Spec;
			Spec.Id = FName(*String(A, TEXT("id")));
			Spec.Type = String(A, TEXT("type"));
			Spec.OutputChannel = static_cast<int32>(Number(A, TEXT("output_channel")));
			Spec.PositionM = Vector3(A, TEXT("position_m"));
			Spec.bCounterClockwise = String(A, TEXT("direction")).Equals(TEXT("ccw"), ESearchCase::IgnoreCase);
			Spec.MaxThrustN = static_cast<float>(Number(A, TEXT("max_thrust_n")));
			Spec.MaxTorqueNm = static_cast<float>(Number(A, TEXT("max_torque_nm")));
			Spec.TimeConstantS = static_cast<float>(Number(A, TEXT("time_constant_s")));
			if (const TArray<TSharedPtr<FJsonValue>>* Curve = Array(A, TEXT("thrust_curve")))
			{
				for (const TSharedPtr<FJsonValue>& PointValue : *Curve)
				{
					const TArray<TSharedPtr<FJsonValue>>& Point = PointValue->AsArray();
					if (Point.Num() == 2)
					{
						Spec.ThrustCurve.Add(FVector2D(Point[0]->AsNumber(), Point[1]->AsNumber()));
					}
				}
			}
			OutSpec.Actuators.Add(MoveTemp(Spec));
		}
	}

	if (const TArray<TSharedPtr<FJsonValue>>* Sensors = Array(Root, TEXT("sensors")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Sensors)
		{
			const TSharedPtr<FJsonObject> S = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!S.IsValid())
			{
				continue;
			}
			FCDSimSensorSpec Spec;
			Spec.Id = FName(*String(S, TEXT("id")));
			Spec.Type = String(S, TEXT("type"));
			Spec.RateHz = static_cast<float>(Number(S, TEXT("rate_hz")));
			const TSharedPtr<FJsonObject> Mount = Object(S, TEXT("mount"));
			Spec.MountPositionM = Vector3(Mount, TEXT("position_m"));
			Spec.MountRotationRpyDeg = Vector3(Mount, TEXT("rotation_deg"));
			Spec.Noise = NumberMap(Object(S, TEXT("noise")));
			Spec.Params = NumberMap(Object(S, TEXT("params")));
			OutSpec.Sensors.Add(MoveTemp(Spec));
		}
	}

	if (const TArray<TSharedPtr<FJsonValue>>* Failures = Array(Root, TEXT("failure_modes")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Failures)
		{
			const TSharedPtr<FJsonObject> F = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!F.IsValid())
			{
				continue;
			}
			FCDSimFailureModeSpec Spec;
			Spec.Id = FName(*String(F, TEXT("id")));
			Spec.Name = String(F, TEXT("name"));
			Spec.Description = String(F, TEXT("description"));
			const TSharedPtr<FJsonObject> Effect = Object(F, TEXT("effect"));
			Spec.EffectType = String(Effect, TEXT("type"));
			Spec.EffectTarget = FName(*String(Effect, TEXT("target")));
			Spec.EffectValue = static_cast<float>(Number(Effect, TEXT("value")));
			Spec.EffectRampS = static_cast<float>(Number(Effect, TEXT("ramp_s")));
			OutSpec.FailureModes.Add(MoveTemp(Spec));
		}
	}

	const TSharedPtr<FJsonObject> Maintenance = Object(Root, TEXT("maintenance"));
	if (const TArray<TSharedPtr<FJsonValue>>* Parts = Array(Maintenance, TEXT("parts")))
	{
		for (const TSharedPtr<FJsonValue>& Value : *Parts)
		{
			const TSharedPtr<FJsonObject> P = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!P.IsValid())
			{
				continue;
			}
			FCDSimMaintenancePartSpec Spec;
			Spec.Id = FName(*String(P, TEXT("id")));
			Spec.Name = String(P, TEXT("name"));
			const TSharedPtr<FJsonObject> Anchor = Object(P, TEXT("anchor"));
			const FString Socket = String(Anchor, TEXT("socket"));
			Spec.Socket = Socket.IsEmpty() ? NAME_None : FName(*Socket);
			Spec.OffsetM = Vector3(Anchor, TEXT("offset_m"));
			OutSpec.MaintenanceParts.Add(MoveTemp(Spec));
		}
	}

	OutSpec.AutopilotType = String(Object(Root, TEXT("autopilot")), TEXT("type"));
	OutSpec.VisualMeshAsset = String(Object(Object(Root, TEXT("meshes")), TEXT("visual")), TEXT("ue_asset"));
	OutSpec.UePlugin = String(Root, TEXT("ue_plugin"));
	return true;
}
