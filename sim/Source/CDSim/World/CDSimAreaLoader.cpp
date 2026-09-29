// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "World/CDSimAreaLoader.h"

#include "CDSim.h"
#include "Components/StaticMeshComponent.h"
#include "Core/CDSimFrames.h"
#include "Core/CDSimJson.h"
#include "Engine/DirectionalLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Misc/Paths.h"
#include "World/CDSimLandingPadActor.h"

namespace
{
	/** /Engine/BasicShapes/Plane is 100 x 100 cm. */
	constexpr double BasicShapeSizeCm = 100.0;
	/** Ground plane margin beyond the area bounds, metres. */
	constexpr double GroundMarginM = 200.0;
} // namespace

bool UCDSimAreaLoader::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

FString UCDSimAreaLoader::GetAreaJsonPath(FName AreaId)
{
	return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Areas"), AreaId.ToString() + TEXT(".json"));
}

bool UCDSimAreaLoader::ParseAreaJson(const FString& JsonText, FCDSimAreaSpec& OutSpec, FString& OutError)
{
	const TSharedPtr<FJsonObject> Root = CDSimJson::ParseObject(JsonText);
	if (!Root.IsValid())
	{
		OutError = TEXT("area JSON is not an object");
		return false;
	}

	OutSpec = FCDSimAreaSpec();
	OutSpec.Id = FName(*CDSimJson::String(Root, TEXT("id")));
	OutSpec.Name = CDSimJson::String(Root, TEXT("name"));
	OutSpec.Version = CDSimJson::String(Root, TEXT("version"));

	const TSharedPtr<FJsonObject> OriginObj = CDSimJson::Object(Root, TEXT("origin"));
	if (!OriginObj.IsValid())
	{
		OutError = TEXT("area JSON has no origin");
		return false;
	}
	OutSpec.OriginLatDeg = CDSimJson::Number(OriginObj, TEXT("lat_deg"));
	OutSpec.OriginLonDeg = CDSimJson::Number(OriginObj, TEXT("lon_deg"));
	OutSpec.OriginAltMslM = CDSimJson::Number(OriginObj, TEXT("alt_msl_m"));

	const TSharedPtr<FJsonObject> Bounds = CDSimJson::Object(Root, TEXT("bounds"));
	OutSpec.MinLatDeg = CDSimJson::Number(Bounds, TEXT("min_lat"));
	OutSpec.MinLonDeg = CDSimJson::Number(Bounds, TEXT("min_lon"));
	OutSpec.MaxLatDeg = CDSimJson::Number(Bounds, TEXT("max_lat"));
	OutSpec.MaxLonDeg = CDSimJson::Number(Bounds, TEXT("max_lon"));

	const TSharedPtr<FJsonObject> Elevation = CDSimJson::Object(Root, TEXT("elevation"));
	OutSpec.ElevationSource = CDSimJson::String(Elevation, TEXT("source"), TEXT("flat"));
	OutSpec.FlatElevationM = CDSimJson::Number(Elevation, TEXT("flat_elevation_m"), OutSpec.OriginAltMslM);

	const TSharedPtr<FJsonObject> Weather = CDSimJson::Object(Root, TEXT("weather"));
	OutSpec.WindSpeedMps = CDSimJson::Number(Weather, TEXT("wind_speed_mps"));
	OutSpec.WindFromDeg = CDSimJson::Number(Weather, TEXT("wind_from_deg"));

	if (const TArray<TSharedPtr<FJsonValue>>* Pads = CDSimJson::Array(Root, TEXT("landing_pads")))
	{
		for (const TSharedPtr<FJsonValue>& PadValue : *Pads)
		{
			const TSharedPtr<FJsonObject> PadObj = PadValue.IsValid() ? PadValue->AsObject() : nullptr;
			if (!PadObj.IsValid())
			{
				continue;
			}
			FCDSimLandingPadSpec Pad;
			Pad.Id = FName(*CDSimJson::String(PadObj, TEXT("id")));
			Pad.Name = CDSimJson::String(PadObj, TEXT("name"));
			const TSharedPtr<FJsonObject> Position = CDSimJson::Object(PadObj, TEXT("position"));
			Pad.LatDeg = CDSimJson::Number(Position, TEXT("lat_deg"));
			Pad.LonDeg = CDSimJson::Number(Position, TEXT("lon_deg"));
			Pad.bHasAltitude = Position.IsValid() && Position->HasField(TEXT("alt_msl_m"));
			Pad.AltMslM = CDSimJson::Number(Position, TEXT("alt_msl_m"));
			Pad.HeadingDeg = CDSimJson::Number(PadObj, TEXT("heading_deg"));
			Pad.SizeM = CDSimJson::Number(PadObj, TEXT("size_m"), 2.0);
			Pad.Marker = CDSimJson::String(PadObj, TEXT("marker"));
			Pad.MarkerId = static_cast<int32>(CDSimJson::Number(PadObj, TEXT("marker_id")));
			OutSpec.LandingPads.Add(MoveTemp(Pad));
		}
	}
	return true;
}

bool UCDSimAreaLoader::LoadArea(FName AreaId)
{
	const FString Path = GetAreaJsonPath(AreaId);
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		UE_LOG(LogCDSim, Error, TEXT("Area '%s': cannot read %s. Run scripts/ue5/export_platform_json.py."),
			*AreaId.ToString(), *Path);
		return false;
	}
	FString Error;
	if (!ParseAreaJson(Text, Spec, Error))
	{
		UE_LOG(LogCDSim, Error, TEXT("Area '%s': %s"), *AreaId.ToString(), *Error);
		return false;
	}
	Origin.LatDeg = Spec.OriginLatDeg;
	Origin.LonDeg = Spec.OriginLonDeg;
	Origin.AltMslM = Spec.OriginAltMslM;
	bLoaded = true;

	if (Spec.ElevationSource != TEXT("flat"))
	{
		UE_LOG(LogCDSim, Warning,
			TEXT("Area '%s' elevation source '%s' not supported in-engine yet; using a flat plane at origin "
				 "altitude. TODO(Phase 2): terrain streaming."),
			*AreaId.ToString(), *Spec.ElevationSource);
		Spec.FlatElevationM = Spec.OriginAltMslM;
	}
	UE_LOG(LogCDSim, Log, TEXT("Area '%s' loaded: origin %.6f, %.6f, %.1f m MSL; %d pads."), *AreaId.ToString(),
		Origin.LatDeg, Origin.LonDeg, Origin.AltMslM, Spec.LandingPads.Num());
	return true;
}

double UCDSimAreaLoader::GetGroundDownM(const FVector& /*PositionNedM*/) const
{
	// Flat areas: ground is at FlatElevationM MSL everywhere. NED down = alt0 - alt.
	// TODO(Phase 2): query the elevation service's heightmap for real terrain.
	return Origin.AltMslM - Spec.FlatElevationM;
}

bool UCDSimAreaLoader::GetPadPositionNed(FName PadId, FVector& OutNedM) const
{
	for (const FCDSimLandingPadSpec& Pad : Spec.LandingPads)
	{
		if (Pad.Id == PadId)
		{
			OutNedM = Origin.GeoToNed(Pad.LatDeg, Pad.LonDeg, Pad.bHasAltitude ? Pad.AltMslM : Spec.FlatElevationM);
			return true;
		}
	}
	return false;
}

FTransform UCDSimAreaLoader::GetHomeSpawnTransform() const
{
	FVector Ned(0.0, 0.0, GetGroundDownM(FVector::ZeroVector));
	double HeadingDeg = 0.0;
	if (Spec.LandingPads.Num() > 0)
	{
		GetPadPositionNed(Spec.LandingPads[0].Id, Ned);
		HeadingDeg = Spec.LandingPads[0].HeadingDeg;
	}
	return FTransform(FRotator(0.0, HeadingDeg, 0.0), CDSimFrames::NedToUeCm(Ned));
}

void UCDSimAreaLoader::SpawnAreaActors()
{
	UWorld* World = GetWorld();
	if (!bLoaded || bActorsSpawned || World == nullptr)
	{
		return;
	}
	bActorsSpawned = true;

	// Runs on the server / standalone only (called from ACDSimGameMode). Pads replicate;
	// the ground plane and sun do not. TODO(Phase 5): fleet clients load the area
	// locally from ACDSimFleetGameState::GetAreaId() (docs/10_ROADMAP.md).

	// Ground plane covering the bounds plus a margin.
	const FVector MinNed = Origin.GeoToNed(Spec.MinLatDeg, Spec.MinLonDeg, Spec.FlatElevationM);
	const FVector MaxNed = Origin.GeoToNed(Spec.MaxLatDeg, Spec.MaxLonDeg, Spec.FlatElevationM);
	const double SizeNorthM = FMath::Abs(MaxNed.X - MinNed.X) + 2.0 * GroundMarginM;
	const double SizeEastM = FMath::Abs(MaxNed.Y - MinNed.Y) + 2.0 * GroundMarginM;
	const FVector CentreNed((MinNed.X + MaxNed.X) * 0.5, (MinNed.Y + MaxNed.Y) * 0.5, GetGroundDownM(FVector::ZeroVector));

	UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	if (AStaticMeshActor* Ground = World->SpawnActor<AStaticMeshActor>(
			AStaticMeshActor::StaticClass(), FTransform(CDSimFrames::NedToUeCm(CentreNed)), Params))
	{
		UStaticMeshComponent* MeshComponent = Ground->GetStaticMeshComponent();
		MeshComponent->SetMobility(EComponentMobility::Movable);
		MeshComponent->SetStaticMesh(PlaneMesh);
		MeshComponent->SetWorldScale3D(FVector(SizeNorthM * CDSimFrames::MetresToCm / BasicShapeSizeCm,
			SizeEastM * CDSimFrames::MetresToCm / BasicShapeSizeCm, 1.0));
#if WITH_EDITOR
		Ground->SetActorLabel(TEXT("CDSim_FlatGround"));
#endif
	}

	// A sun so the placeholder world is visible. TODO(Phase 2): time-of-day from area weather.
	World->SpawnActor<ADirectionalLight>(
		ADirectionalLight::StaticClass(), FTransform(FRotator(-50.0, 30.0, 0.0), FVector(0.0, 0.0, 10000.0)), Params);

	for (const FCDSimLandingPadSpec& Pad : Spec.LandingPads)
	{
		FVector PadNed;
		GetPadPositionNed(Pad.Id, PadNed);
		const FTransform PadTransform(FRotator(0.0, Pad.HeadingDeg, 0.0), CDSimFrames::NedToUeCm(PadNed));
		if (ACDSimLandingPadActor* PadActor =
				World->SpawnActor<ACDSimLandingPadActor>(ACDSimLandingPadActor::StaticClass(), PadTransform, Params))
		{
			PadActor->InitialisePad(Pad);
			SpawnedPads.Add(PadActor);
		}
	}
	UE_LOG(LogCDSim, Log, TEXT("Area '%s': spawned ground %.0f x %.0f m and %d pads."), *Spec.Id.ToString(),
		SizeNorthM, SizeEastM, SpawnedPads.Num());
}
