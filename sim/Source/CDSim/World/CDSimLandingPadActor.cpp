// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "World/CDSimLandingPadActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr double PadThicknessM = 0.05;
	constexpr double BasicShapeSizeCm = 100.0;
} // namespace

ACDSimLandingPadActor::ACDSimLandingPadActor()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = true; // Spawned by the server in fleet mode; clients receive PadSpec via OnRep.

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	PadMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PadMesh"));
	PadMesh->SetupAttachment(Root);
	PadMesh->SetCollisionProfileName(TEXT("BlockAll"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		PadMesh->SetStaticMesh(CubeMesh.Object);
	}
}

void ACDSimLandingPadActor::InitialisePad(const FCDSimLandingPadSpec& InSpec)
{
	PadSpec = InSpec;
	ApplyPadSpec();
}

void ACDSimLandingPadActor::OnRep_PadSpec()
{
	ApplyPadSpec();
}

void ACDSimLandingPadActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ACDSimLandingPadActor, PadSpec);
}

void ACDSimLandingPadActor::ApplyPadSpec()
{
	const double SideCm = PadSpec.SizeM * 100.0;
	const double ThicknessCm = PadThicknessM * 100.0;
	// Cube is centred on its pivot: lift it so its top face sits just above the ground.
	PadMesh->SetRelativeScale3D(
		FVector(SideCm / BasicShapeSizeCm, SideCm / BasicShapeSizeCm, ThicknessCm / BasicShapeSizeCm));
	PadMesh->SetRelativeLocation(FVector(0.0, 0.0, ThicknessCm * 0.5));
#if WITH_EDITOR
	SetActorLabel(FString::Printf(TEXT("Pad_%s"), *PadSpec.Id.ToString()));
#endif
	// TODO(Phase 7): marker material (AprilTag id PadSpec.MarkerId).
}
