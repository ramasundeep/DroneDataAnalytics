// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Core/CDSimGameMode.h"

#include "CDSim.h"
#include "Core/CDSimClockSubsystem.h"
#include "Core/CDSimGameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Net/CDSimFleetGameState.h"
#include "Net/CDSimPlayerState.h"
#include "Net/CDSimSessionCode.h"
#include "Vehicle/CDSimVehiclePawn.h"
#include "World/CDSimAreaLoader.h"

ACDSimGameMode::ACDSimGameMode()
{
	DefaultPawnClass = ACDSimVehiclePawn::StaticClass();
	GameStateClass = ACDSimFleetGameState::StaticClass();
	PlayerStateClass = ACDSimPlayerState::StaticClass();
}

void ACDSimGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	const UCDSimGameInstance* GameInstance = Cast<UCDSimGameInstance>(GetGameInstance());
	if (GameInstance == nullptr)
	{
		UE_LOG(LogCDSim, Error, TEXT("GameInstanceClass is not UCDSimGameInstance; check Config/DefaultEngine.ini."));
		return;
	}
	if (UCDSimAreaLoader* Area = GetWorld()->GetSubsystem<UCDSimAreaLoader>())
	{
		Area->LoadArea(GameInstance->GetAreaId());
	}
}

void ACDSimGameMode::StartPlay()
{
	const UCDSimGameInstance* GameInstance = Cast<UCDSimGameInstance>(GetGameInstance());
	if (ACDSimFleetGameState* FleetState = GetGameState<ACDSimFleetGameState>())
	{
		const FString Code = UCDSimSessionCode::GenerateSessionCode();
		FleetState->SetSessionInfo(GameInstance != nullptr ? GameInstance->GetSessionId() : FString(), Code,
			GameInstance != nullptr ? GameInstance->GetAreaId() : NAME_None);
		if (GetNetMode() == NM_DedicatedServer || GetNetMode() == NM_ListenServer)
		{
			UE_LOG(LogCDSim, Log, TEXT("Fleet session code: %s"), *Code);
		}
	}

	if (UCDSimAreaLoader* Area = GetWorld()->GetSubsystem<UCDSimAreaLoader>())
	{
		Area->SpawnAreaActors();
	}

	Super::StartPlay();

	if (UCDSimClockSubsystem* Clock = GetWorld()->GetSubsystem<UCDSimClockSubsystem>())
	{
		// TODO(Phase 7): RL harness switches the clock to Stepped mode over gRPC.
		Clock->Resume();
	}
}

FString ACDSimGameMode::InitNewPlayer(
	APlayerController* NewPlayerController, const FUniqueNetIdRepl& UniqueId, const FString& Options, const FString& Portal)
{
	const FString Result = Super::InitNewPlayer(NewPlayerController, UniqueId, Options, Portal);
	if (NewPlayerController != nullptr)
	{
		if (ACDSimPlayerState* PlayerState = NewPlayerController->GetPlayerState<ACDSimPlayerState>())
		{
			const FString TraineeId = UGameplayStatics::ParseOption(Options, TEXT("Trainee"));
			PlayerState->SetTraineeId(TraineeId.IsEmpty() ? TEXT("trainee") : TraineeId);
		}
	}
	return Result;
}

void ACDSimGameMode::RestartPlayer(AController* NewPlayer)
{
	if (!IsValid(NewPlayer))
	{
		return;
	}
	// Spawn on the area's home pad rather than a PlayerStart (the placeholder map has none).
	FTransform SpawnTransform = FTransform::Identity;
	if (const UCDSimAreaLoader* Area = GetWorld()->GetSubsystem<UCDSimAreaLoader>())
	{
		if (Area->IsAreaLoaded())
		{
			SpawnTransform = Area->GetHomeSpawnTransform();
		}
	}
	RestartPlayerAtTransform(NewPlayer, SpawnTransform);
}

APawn* ACDSimGameMode::SpawnDefaultPawnAtTransform_Implementation(AController* NewPlayer, const FTransform& SpawnTransform)
{
	UClass* PawnClass = GetDefaultPawnClassForController(NewPlayer);
	if (PawnClass == nullptr || !PawnClass->IsChildOf(ACDSimVehiclePawn::StaticClass()))
	{
		return Super::SpawnDefaultPawnAtTransform_Implementation(NewPlayer, SpawnTransform);
	}

	const UCDSimGameInstance* GameInstance = Cast<UCDSimGameInstance>(GetGameInstance());
	const FName PlatformId = GameInstance != nullptr ? GameInstance->GetPlatformId() : FName(TEXT("cdpl_quad_01"));
	const FString VehicleId = FString::Printf(TEXT("veh_%02d"), NextVehicleIndex++);

	ACDSimVehiclePawn* Pawn = GetWorld()->SpawnActorDeferred<ACDSimVehiclePawn>(
		PawnClass, SpawnTransform, nullptr, GetInstigator(), ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (Pawn == nullptr)
	{
		UE_LOG(LogCDSim, Error, TEXT("Failed to spawn vehicle pawn for platform '%s'."), *PlatformId.ToString());
		return nullptr;
	}
	Pawn->ConfigurePlatform(PlatformId, VehicleId);
	Pawn->FinishSpawning(SpawnTransform);

	if (NewPlayer != nullptr)
	{
		if (ACDSimPlayerState* PlayerState = NewPlayer->GetPlayerState<ACDSimPlayerState>())
		{
			PlayerState->SetVehicleId(VehicleId);
		}
	}
	UE_LOG(LogCDSim, Log, TEXT("Spawned %s (platform '%s')."), *VehicleId, *PlatformId.ToString());
	return Pawn;
}
