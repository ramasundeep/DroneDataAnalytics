// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Vehicle/CDSimPlatformRegistry.h"

#include "CDSim.h"
#include "Core/CDSimJson.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"

void UCDSimPlatformRegistry::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	ReloadPlatforms();
}

void UCDSimPlatformRegistry::Deinitialize()
{
	Platforms.Reset();
	Super::Deinitialize();
}

FString UCDSimPlatformRegistry::GetPlatformJsonDir()
{
	return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Platforms"));
}

int32 UCDSimPlatformRegistry::ReloadPlatforms()
{
	Platforms.Reset();

	const FString Dir = GetPlatformJsonDir();
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(Dir, TEXT("*.json")), /*Files=*/true, /*Directories=*/false);
	if (Files.Num() == 0)
	{
		UE_LOG(LogCDSim, Error,
			TEXT("No platform JSON in %s. Run: python scripts/ue5/export_platform_json.py (see docs/BUILDING_UE5.md)."),
			*Dir);
		return 0;
	}

	for (const FString& File : Files)
	{
		const FString Path = FPaths::Combine(Dir, File);
		TSharedPtr<FJsonObject> Root;
		FString Error;
		FCDSimPlatformSpec Spec;
		if (!CDSimJson::LoadFile(Path, Root, Error) || !FCDSimPlatformSpec::FromJson(Root, Spec, Error))
		{
			UE_LOG(LogCDSim, Error, TEXT("Skipping platform %s: %s"), *Path, *Error);
			continue;
		}
		if (Spec.Id.ToString() != FPaths::GetBaseFilename(File))
		{
			UE_LOG(LogCDSim, Warning, TEXT("Platform file %s declares id '%s'; using the declared id."), *File,
				*Spec.Id.ToString());
		}
		UE_LOG(LogCDSim, Log, TEXT("Platform '%s' (%s, %s, %.2f kg, %d actuators, %d sensors)."), *Spec.Id.ToString(),
			*Spec.Class, *Spec.Status, Spec.MassKg, Spec.Actuators.Num(), Spec.Sensors.Num());
		Platforms.Add(Spec.Id, MoveTemp(Spec));
	}
	return Platforms.Num();
}

bool UCDSimPlatformRegistry::GetPlatform(FName PlatformId, FCDSimPlatformSpec& OutSpec) const
{
	if (const FCDSimPlatformSpec* Found = FindPlatform(PlatformId))
	{
		OutSpec = *Found;
		return true;
	}
	return false;
}

const FCDSimPlatformSpec* UCDSimPlatformRegistry::FindPlatform(FName PlatformId) const
{
	return Platforms.Find(PlatformId);
}

TArray<FName> UCDSimPlatformRegistry::GetPlatformIds() const
{
	TArray<FName> Ids;
	Platforms.GetKeys(Ids);
	return Ids;
}
