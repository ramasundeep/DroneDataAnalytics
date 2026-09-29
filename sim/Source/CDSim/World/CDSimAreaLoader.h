// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "World/CDSimAreaSpec.h"
#include "World/CDSimGeo.h"

#include "CDSimAreaLoader.generated.h"

class ACDSimLandingPadActor;

/**
 * Loads an area package into the current world.
 *
 * Reads sim/Config/Areas/<id>.json (generated from terrain/areas/<id>/area.yaml
 * by scripts/ue5/export_platform_json.py — UE has no YAML parser), fixes the UE
 * world origin at the area origin (see Core/CDSimFrames.h for axes), and spawns:
 *   - a flat ground plane for `elevation.source: flat` areas;
 *   - one ACDSimLandingPadActor per `landing_pads[]` entry.
 *
 * Geodetic conversion uses the flat-earth approximation in World/CDSimGeo.h.
 * TODO(Phase 2): stream terrain tiles / meshes from the offline terrain
 * services instead of a flat plane (docs/10_ROADMAP.md).
 */
UCLASS()
class CDSIM_API UCDSimAreaLoader : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** Parse the area JSON. Does not spawn anything. Returns false (and logs) on error. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Area")
	bool LoadArea(FName AreaId);

	/** Spawn ground, light and pad actors for the loaded area. Call once, server/standalone. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Area")
	void SpawnAreaActors();

	UFUNCTION(BlueprintPure, Category = "CDSim|Area")
	bool IsAreaLoaded() const { return bLoaded; }

	const FCDSimAreaSpec& GetAreaSpec() const { return Spec; }

	const FCDSimGeoOrigin& GetGeoOrigin() const { return Origin; }

	/** NED "down" coordinate of the ground at a local position. Flat areas: constant. */
	double GetGroundDownM(const FVector& PositionNedM) const;

	/** Local NED position (metres) of a pad centre, on the ground. */
	bool GetPadPositionNed(FName PadId, FVector& OutNedM) const;

	/** UE world transform for spawning a vehicle on the first pad (usually "pad_home"). */
	FTransform GetHomeSpawnTransform() const;

	/** Absolute path of the JSON file for an area id. */
	static FString GetAreaJsonPath(FName AreaId);

	/** Parse area JSON text into a spec. Exposed for automation tests. */
	static bool ParseAreaJson(const FString& JsonText, FCDSimAreaSpec& OutSpec, FString& OutError);

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	UPROPERTY()
	FCDSimAreaSpec Spec;

	UPROPERTY()
	TArray<TObjectPtr<ACDSimLandingPadActor>> SpawnedPads;

	FCDSimGeoOrigin Origin;
	bool bLoaded = false;
	bool bActorsSpawned = false;
};
