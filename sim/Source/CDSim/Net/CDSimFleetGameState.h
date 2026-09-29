// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"

#include "CDSimFleetGameState.generated.h"

/**
 * Replicated session state for fleet mode (dedicated server + LAN clients,
 * docs/ADR/0010). Also used single-seat, where it simply is not replicated
 * anywhere.
 *
 * Carries the session identity, the 6-character LAN join code, the area id
 * (so clients can load the same area locally) and the authoritative sim time,
 * which the server republishes at ~10 Hz.
 *
 * TODO(Phase 5): clients interpolate SimTimeUs between updates and load the
 * area locally from AreaId; instructor pause/rate controls replicate from here
 * (docs/10_ROADMAP.md).
 */
UCLASS()
class CDSIM_API ACDSimFleetGameState : public AGameStateBase
{
	GENERATED_BODY()

public:
	ACDSimFleetGameState();

	virtual void Tick(float DeltaSeconds) override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Server only. */
	void SetSessionInfo(const FString& InSessionId, const FString& InSessionCode, FName InAreaId);

	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	FString GetSessionId() const { return SessionId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	FString GetSessionCode() const { return SessionCode; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	FName GetAreaId() const { return AreaId; }

	/** Last sim time received from the server (clients) or current (server). */
	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	int64 GetReplicatedSimTimeUs() const { return ReplicatedSimTimeUs; }

protected:
	UPROPERTY(Replicated, VisibleInstanceOnly, Category = "CDSim|Fleet")
	FString SessionId;

	UPROPERTY(Replicated, VisibleInstanceOnly, Category = "CDSim|Fleet")
	FString SessionCode;

	UPROPERTY(Replicated, VisibleInstanceOnly, Category = "CDSim|Fleet")
	FName AreaId;

	UPROPERTY(Replicated, VisibleInstanceOnly, Category = "CDSim|Fleet")
	int64 ReplicatedSimTimeUs = 0;

	/** Seconds between sim-time publications. */
	UPROPERTY(EditAnywhere, Category = "CDSim|Fleet")
	float SimTimePublishIntervalS = 0.1f;

private:
	float SecondsSincePublish = 0.0f;
};
