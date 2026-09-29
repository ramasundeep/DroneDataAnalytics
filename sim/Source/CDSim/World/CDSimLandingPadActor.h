// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "World/CDSimAreaSpec.h"

#include "CDSimLandingPadActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;

/**
 * A landing pad from area.yaml `landing_pads[]`. Placeholder visual: a thin
 * square slab built from /Engine/BasicShapes/Cube, SizeM on a side.
 * TODO(Phase 7): AprilTag marker material (marker / marker_id) for the
 * precision-landing curriculum (docs/10_ROADMAP.md).
 */
UCLASS()
class CDSIM_API ACDSimLandingPadActor : public AActor
{
	GENERATED_BODY()

public:
	ACDSimLandingPadActor();

	/** Apply the pad spec (size, id, marker). Call right after spawning. */
	void InitialisePad(const FCDSimLandingPadSpec& InSpec);

	UFUNCTION(BlueprintPure, Category = "CDSim|Area")
	FName GetPadId() const { return PadSpec.Id; }

	const FCDSimLandingPadSpec& GetPadSpec() const { return PadSpec; }

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

protected:
	UFUNCTION()
	void OnRep_PadSpec();

	/** Scales / labels the mesh from PadSpec. Runs on server and (via OnRep) on clients. */
	void ApplyPadSpec();

	UPROPERTY(VisibleAnywhere, Category = "CDSim|Area")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, Category = "CDSim|Area")
	TObjectPtr<UStaticMeshComponent> PadMesh;

	UPROPERTY(VisibleInstanceOnly, ReplicatedUsing = OnRep_PadSpec, Category = "CDSim|Area")
	FCDSimLandingPadSpec PadSpec;
};
