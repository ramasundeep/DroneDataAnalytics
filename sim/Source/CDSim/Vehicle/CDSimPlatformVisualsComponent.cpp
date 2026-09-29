// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Vehicle/CDSimPlatformVisualsComponent.h"

#include "CDSim.h"
#include "Components/StaticMeshComponent.h"
#include "Core/CDSimFrames.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Vehicle/CDSimPlatformSpec.h"

namespace
{
	/** All /Engine/BasicShapes meshes are 100 cm across. */
	constexpr double BasicShapeSizeCm = 100.0;
} // namespace

// --------------------------------------------------------------------------
// UCDSimPlatformVisualsComponent
// --------------------------------------------------------------------------

UStaticMesh* UCDSimPlatformVisualsComponent::LoadBasicShape(ECDSimBasicShape Shape)
{
	const TCHAR* Path = TEXT("/Engine/BasicShapes/Cube.Cube");
	switch (Shape)
	{
	case ECDSimBasicShape::Cylinder:
		Path = TEXT("/Engine/BasicShapes/Cylinder.Cylinder");
		break;
	case ECDSimBasicShape::Sphere:
		Path = TEXT("/Engine/BasicShapes/Sphere.Sphere");
		break;
	case ECDSimBasicShape::Cone:
		Path = TEXT("/Engine/BasicShapes/Cone.Cone");
		break;
	case ECDSimBasicShape::Plane:
		Path = TEXT("/Engine/BasicShapes/Plane.Plane");
		break;
	case ECDSimBasicShape::Cube:
	default:
		break;
	}
	return LoadObject<UStaticMesh>(nullptr, Path);
}

UStaticMeshComponent* UCDSimPlatformVisualsComponent::AddBasicShape(
	FName Name, ECDSimBasicShape Shape, const FVector& LocationCm, const FVector& SizeCm, const FRotator& Rotation)
{
	AActor* Owner = GetOwner();
	if (Owner == nullptr)
	{
		return nullptr;
	}
	UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(Owner, Name);
	Mesh->SetStaticMesh(LoadBasicShape(Shape));
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetupAttachment(this);
	Mesh->SetRelativeLocationAndRotation(LocationCm, Rotation);
	Mesh->SetRelativeScale3D(SizeCm / BasicShapeSizeCm);
	Mesh->RegisterComponent();
	Owner->AddInstanceComponent(Mesh);
	PartMeshes.Add(Mesh);
	return Mesh;
}

USceneComponent* UCDSimPlatformVisualsComponent::AddPartAnchor(FName SocketName, const FVector& LocationCm)
{
	AActor* Owner = GetOwner();
	if (Owner == nullptr)
	{
		return nullptr;
	}
	USceneComponent* Anchor = NewObject<USceneComponent>(Owner, SocketName);
	Anchor->SetupAttachment(this);
	Anchor->SetRelativeLocation(LocationCm);
	Anchor->RegisterComponent();
	Owner->AddInstanceComponent(Anchor);
	PartAnchors.Add(SocketName, Anchor);
	return Anchor;
}

USceneComponent* UCDSimPlatformVisualsComponent::FindPartAnchor(FName SocketName) const
{
	const TObjectPtr<USceneComponent>* Found = PartAnchors.Find(SocketName);
	return Found != nullptr ? Found->Get() : nullptr;
}

FTransform UCDSimPlatformVisualsComponent::GetPartAnchorTransform(FName SocketName) const
{
	if (const USceneComponent* Anchor = FindPartAnchor(SocketName))
	{
		return Anchor->GetComponentTransform();
	}
	return GetComponentTransform();
}

void UCDSimPlatformVisualsComponent::BuildVisuals(const FCDSimPlatformSpec& Spec)
{
	// Generic placeholder: 20 x 20 x 8 cm body and a 25 cm disc per actuator.
	AddBasicShape(TEXT("Placeholder_Body"), ECDSimBasicShape::Cube, FVector::ZeroVector, FVector(20.0, 20.0, 8.0));
	for (const FCDSimActuatorSpec& Actuator : Spec.Actuators)
	{
		const FVector LocationCm = CDSimFrames::FrdToUeBodyCm(Actuator.PositionM) + FVector(0.0, 0.0, 5.0);
		AddBasicShape(FName(*FString::Printf(TEXT("Placeholder_Rotor_%s"), *Actuator.Id.ToString())),
			ECDSimBasicShape::Cylinder, LocationCm, FVector(25.0, 25.0, 1.0));
	}
	UE_LOG(LogCDSim, Log, TEXT("Platform '%s': generic placeholder visuals (no platform plugin registered)."),
		*Spec.Id.ToString());
}

// --------------------------------------------------------------------------
// FCDSimPlatformVisualsRegistry
// --------------------------------------------------------------------------

TMap<FName, FSoftClassPath>& FCDSimPlatformVisualsRegistry::GetMap()
{
	static TMap<FName, FSoftClassPath> Map;
	return Map;
}

void FCDSimPlatformVisualsRegistry::Register(FName PlatformId, const FSoftClassPath& VisualsClass)
{
	GetMap().Add(PlatformId, VisualsClass);
	UE_LOG(LogCDSim, Log, TEXT("Platform '%s' visuals registered: %s"), *PlatformId.ToString(),
		*VisualsClass.ToString());
}

void FCDSimPlatformVisualsRegistry::Unregister(FName PlatformId)
{
	GetMap().Remove(PlatformId);
}

UClass* FCDSimPlatformVisualsRegistry::ResolveVisualsClass(FName PlatformId)
{
	if (const FSoftClassPath* Path = GetMap().Find(PlatformId))
	{
		if (UClass* Class = Path->TryLoadClass<UCDSimPlatformVisualsComponent>())
		{
			return Class;
		}
		UE_LOG(LogCDSim, Warning, TEXT("Platform '%s': cannot load visuals class %s; using generic placeholder."),
			*PlatformId.ToString(), *Path->ToString());
	}
	return UCDSimPlatformVisualsComponent::StaticClass();
}
