// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// In-engine view of terrain/areas/<id>/area.yaml (exported to
// sim/Config/Areas/<id>.json by scripts/ue5/export_platform_json.py).
// Only the fields the engine needs today are mirrored; the YAML + JSON Schema
// (schemas/json/area.schema.json) remain the source of truth.

#pragma once

#include "CoreMinimal.h"

#include "CDSimAreaSpec.generated.h"

/** area.yaml landing_pads[] */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimLandingPadSpec
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FName Id;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double LatDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double LonDeg = 0.0;

	/** Optional; if absent the pad sits on the ground elevation. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double AltMslM = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	bool bHasAltitude = false;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double HeadingDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double SizeM = 2.0;

	/** e.g. "apriltag". */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FString Marker;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	int32 MarkerId = 0;
};

/** area.yaml (subset). */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimAreaSpec
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FName Id;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FString Version;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double OriginLatDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double OriginLonDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double OriginAltMslM = 0.0;

	/** elevation.source, e.g. "flat". */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	FString ElevationSource;

	/** elevation.flat_elevation_m (MSL); only meaningful when ElevationSource == "flat". */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double FlatElevationM = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double MinLatDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double MinLonDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double MaxLatDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double MaxLonDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	TArray<FCDSimLandingPadSpec> LandingPads;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double WindSpeedMps = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Area")
	double WindFromDeg = 0.0;
};
