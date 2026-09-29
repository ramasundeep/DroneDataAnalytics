// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// In-engine view of platforms/<id>/platform.yaml (exported to
// sim/Config/Platforms/<id>.json by scripts/ue5/export_platform_json.py).
// Frames and units are those of platform.yaml: body FRD, metres, kg, N, N*m.
// The YAML + schemas/json/platform.schema.json remain the source of truth.

#pragma once

#include "CoreMinimal.h"

#include "CDSimPlatformSpec.generated.h"

class FJsonObject;

/** platform.yaml propulsion.actuators[] */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimActuatorSpec
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName Id;

	/** e.g. "motor", "servo". */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Type;

	/** 1-based autopilot output channel (SERVOn). */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	int32 OutputChannel = 0;

	/** Position in body FRD, metres. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector PositionM = FVector::ZeroVector;

	/** Rotor spin direction seen from above: true = counter-clockwise ("ccw"). */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	bool bCounterClockwise = false;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float MaxThrustN = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float MaxTorqueNm = 0.0f;

	/** First-order motor lag. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float TimeConstantS = 0.0f;

	/** (command 0..1, thrust fraction 0..1) points, ascending in command. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TArray<FVector2D> ThrustCurve;

	/** Piecewise-linear thrust fraction for a normalised command. Linear if no curve. */
	double EvaluateThrustFraction(double Command) const { return EvaluateCurve(ThrustCurve, Command); }

	/** Piecewise-linear lookup in (x ascending, y) points; identity if fewer than 2 points. */
	static double EvaluateCurve(const TArray<FVector2D>& Curve, double Command);
};

/** platform.yaml sensors[] */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimSensorSpec
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName Id;

	/** imu, baro, mag, gps, rangefinder, camera, ... */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Type;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float RateHz = 0.0f;

	/** mount.position_m, body FRD metres. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector MountPositionM = FVector::ZeroVector;

	/** mount.rotation_deg as (roll, pitch, yaw) in FRD. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector MountRotationRpyDeg = FVector::ZeroVector;

	/** noise.* numeric members, e.g. gyro_noise_radps. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TMap<FName, float> Noise;

	/** params.* numeric members, e.g. width_px, hfov_deg. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TMap<FName, float> Params;

	float GetNoise(FName Key, float Default = 0.0f) const;
	float GetParam(FName Key, float Default = 0.0f) const;
};

/** platform.yaml failure_modes[] */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimFailureModeSpec
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName Id;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Description;

	/** effect.type: actuator_scale, sensor_dropout, sensor_bias, battery_sag, comms_loss. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString EffectType;

	/** effect.target: actuator or sensor id (may be empty). */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName EffectTarget;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float EffectValue = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float EffectRampS = 0.0f;
};

/** platform.yaml maintenance.parts[] (only what the engine anchors to). */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimMaintenancePartSpec
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName Id;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Name;

	/** anchor.socket, e.g. SOCKET_Prop_M1. None if the part uses an offset. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName Socket;

	/** anchor.offset_m, body FRD metres (used when Socket is None). */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector OffsetM = FVector::ZeroVector;
};

/** platform.yaml, the subset the engine consumes. */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimPlatformSpec
{
	GENERATED_BODY()

	/** identity.id — also the plugin suffix: CDSimPlatform_<id>. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FName Id;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Version;

	/** identity.status, e.g. "placeholder". */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Status;

	/** class: multirotor, fixed_wing, vtol, ground, ... */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString Class;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	float MassKg = 0.0f;

	/** mass_properties.cg_m, body FRD metres. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector CgM = FVector::ZeroVector;

	/** Principal inertia (ixx, iyy, izz), kg*m^2. Products of inertia ignored. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector InertiaKgm2 = FVector::OneVector;

	/** aero.drag_coefficients, body FRD, linear drag N per m/s. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FVector LinearDragFrd = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TArray<FCDSimActuatorSpec> Actuators;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TArray<FCDSimSensorSpec> Sensors;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TArray<FCDSimFailureModeSpec> FailureModes;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	TArray<FCDSimMaintenancePartSpec> MaintenanceParts;

	/** autopilot.type: "ardupilot" (PX4 later). */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString AutopilotType;

	/** meshes.visual.ue_asset. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString VisualMeshAsset;

	/** ue_plugin, e.g. CDSimPlatform_cdpl_quad_01. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Platform")
	FString UePlugin;

	const FCDSimActuatorSpec* FindActuator(FName ActuatorId) const;
	const FCDSimFailureModeSpec* FindFailureMode(FName FailureId) const;

	/** Parse the exported platform JSON. Returns false and sets OutError on failure. */
	static bool FromJson(const TSharedPtr<FJsonObject>& Root, FCDSimPlatformSpec& OutSpec, FString& OutError);
};
