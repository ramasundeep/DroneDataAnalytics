// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerState.h"

#include "CDSimPlayerState.generated.h"

/**
 * Per-seat identity, replicated to every client in fleet mode: which trainee
 * sits in this seat and which vehicle they fly. Used as Header.actorId.
 *
 * TraineeId comes from the join URL option ?Trainee=<id> (ACDSimGameMode::InitNewPlayer).
 * TODO(Phase 5): validate it against the API service's session roster.
 */
UCLASS()
class CDSIM_API ACDSimPlayerState : public APlayerState
{
	GENERATED_BODY()

public:
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Server only. */
	void SetTraineeId(const FString& InTraineeId) { TraineeId = InTraineeId; }

	/** Server only. */
	void SetVehicleId(const FString& InVehicleId) { VehicleId = InVehicleId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	FString GetTraineeId() const { return TraineeId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	FString GetVehicleId() const { return VehicleId; }

protected:
	UPROPERTY(Replicated, VisibleInstanceOnly, Category = "CDSim|Fleet")
	FString TraineeId;

	UPROPERTY(Replicated, VisibleInstanceOnly, Category = "CDSim|Fleet")
	FString VehicleId;
};
