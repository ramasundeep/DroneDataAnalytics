// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "UObject/SoftObjectPath.h"

#include "CDSimPlatformVisualsComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
struct FCDSimPlatformSpec;

/** Which /Engine/BasicShapes mesh to use for a placeholder part. */
UENUM()
enum class ECDSimBasicShape : uint8
{
	Cube,
	Cylinder,
	Sphere,
	Cone,
	Plane,
};

/**
 * Visual representation of a platform, attached to ACDSimVehiclePawn.
 * Visual ONLY: no collision, no physics — dynamics live in FCDSimRigidBody.
 *
 * This base class builds a generic placeholder (a body box plus one disc per
 * actuator) from any FCDSimPlatformSpec, so a platform with no plugin still
 * appears. A platform plugin (sim/Plugins/CDSimPlatform_<id>/) subclasses it
 * to add a specific look and the named part anchors from platform.yaml
 * `maintenance.parts[].anchor.socket` (e.g. SOCKET_Prop_M1), and registers the
 * subclass with FCDSimPlatformVisualsRegistry in its module StartupModule().
 *
 * Anchors are named child scene components. When real CAD arrives the same
 * names become sockets on the static mesh asset (docs/04_PLATFORM_PLUGIN_SPEC.md)
 * and FindPartAnchor() keeps working for callers.
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIM_API UCDSimPlatformVisualsComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	/** Build child meshes and anchors. Called once by the pawn after the component is registered. */
	virtual void BuildVisuals(const FCDSimPlatformSpec& Spec);

	/** World transform of a named part anchor (socket), or the component transform if unknown. */
	UFUNCTION(BlueprintPure, Category = "CDSim|Visuals")
	FTransform GetPartAnchorTransform(FName SocketName) const;

	/** Anchor component by socket name, or nullptr. */
	USceneComponent* FindPartAnchor(FName SocketName) const;

	/** Spin visuals for rotors, normalised outputs in spec order. Default: no-op. */
	virtual void UpdateActuatorVisuals(const TArray<double>& NormalisedOutputs) {}

protected:
	/** Create a no-collision basic-shape mesh child. SizeCm is the full extent along each axis. */
	UStaticMeshComponent* AddBasicShape(FName Name, ECDSimBasicShape Shape, const FVector& LocationCm,
		const FVector& SizeCm, const FRotator& Rotation = FRotator::ZeroRotator);

	/** Create a named anchor (socket stand-in) at a body-relative UE location. */
	USceneComponent* AddPartAnchor(FName SocketName, const FVector& LocationCm);

	static UStaticMesh* LoadBasicShape(ECDSimBasicShape Shape);

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> PartMeshes;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<USceneComponent>> PartAnchors;
};

/**
 * Process-wide map of platform id -> visuals component class. Platform plugins
 * register in StartupModule() and unregister in ShutdownModule(). Class paths
 * (not UClass pointers) are stored so registration is safe before UObject
 * initialisation completes; they are resolved when a pawn is spawned.
 */
class CDSIM_API FCDSimPlatformVisualsRegistry
{
public:
	static void Register(FName PlatformId, const FSoftClassPath& VisualsClass);
	static void Unregister(FName PlatformId);

	/** Registered class for PlatformId, or UCDSimPlatformVisualsComponent (generic placeholder). */
	static UClass* ResolveVisualsClass(FName PlatformId);

private:
	static TMap<FName, FSoftClassPath>& GetMap();
};
