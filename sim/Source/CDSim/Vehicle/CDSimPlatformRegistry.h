// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Vehicle/CDSimPlatformSpec.h"

#include "CDSimPlatformRegistry.generated.h"

/**
 * Registry of every platform the engine can spawn.
 *
 * UE has no YAML parser, so platforms/<id>/platform.yaml is converted at build
 * time into sim/Config/Platforms/<id>.json by scripts/ue5/export_platform_json.py
 * (run automatically by scripts/ue5/build.sh / build.ps1; run it by hand before
 * opening the editor). The JSON is a 1:1 copy of the YAML tree; this registry
 * parses it into FCDSimPlatformSpec on game-instance start.
 *
 * Adding a platform never needs a change here (CLAUDE.md "How to add a platform").
 */
UCLASS()
class CDSIM_API UCDSimPlatformRegistry : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** Re-scan the exported platform JSON directory. Returns the number of platforms loaded. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Platform")
	int32 ReloadPlatforms();

	/** Copy of the spec for PlatformId. Returns false if unknown. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Platform")
	bool GetPlatform(FName PlatformId, FCDSimPlatformSpec& OutSpec) const;

	/** Pointer into the registry (valid until the next ReloadPlatforms), or nullptr. */
	const FCDSimPlatformSpec* FindPlatform(FName PlatformId) const;

	UFUNCTION(BlueprintPure, Category = "CDSim|Platform")
	TArray<FName> GetPlatformIds() const;

	/** Directory holding the exported platform JSON. */
	static FString GetPlatformJsonDir();

private:
	UPROPERTY()
	TMap<FName, FCDSimPlatformSpec> Platforms;
};
