// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"

#include "CDSimGameMode.generated.h"

/**
 * Session orchestration (server / standalone only — game modes do not exist
 * on clients):
 *   InitGame   -> load the area JSON (-Area=), publish session info to the game state
 *   RestartPlayer -> spawn one ACDSimVehiclePawn per player on the home pad,
 *                 configured with the platform (-Platform=) and a vehicle id
 *   StartPlay  -> spawn ground/pads, start the sim clock
 *
 * Works for single-seat and for the fleet dedicated server (one vehicle per
 * connected seat). TODO(Phase 4): scenario runner drives spawn points and
 * injects; TODO(Phase 5): per-seat SITL ports and spawn offsets (docs/10_ROADMAP.md).
 */
UCLASS()
class CDSIM_API ACDSimGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ACDSimGameMode();

	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
	virtual void StartPlay() override;
	virtual FString InitNewPlayer(APlayerController* NewPlayerController, const FUniqueNetIdRepl& UniqueId,
		const FString& Options, const FString& Portal = TEXT("")) override;
	virtual void RestartPlayer(AController* NewPlayer) override;
	virtual APawn* SpawnDefaultPawnAtTransform_Implementation(AController* NewPlayer, const FTransform& SpawnTransform) override;

private:
	int32 NextVehicleIndex = 1;
};
