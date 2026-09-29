// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Net/CDSimFleetGameState.h"

#include "Core/CDSimClockSubsystem.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"

ACDSimFleetGameState::ACDSimFleetGameState()
{
	PrimaryActorTick.bCanEverTick = true;
}

void ACDSimFleetGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ACDSimFleetGameState, SessionId);
	DOREPLIFETIME(ACDSimFleetGameState, SessionCode);
	DOREPLIFETIME(ACDSimFleetGameState, AreaId);
	DOREPLIFETIME(ACDSimFleetGameState, ReplicatedSimTimeUs);
}

void ACDSimFleetGameState::SetSessionInfo(const FString& InSessionId, const FString& InSessionCode, FName InAreaId)
{
	SessionId = InSessionId;
	SessionCode = InSessionCode;
	AreaId = InAreaId;
}

void ACDSimFleetGameState::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!HasAuthority())
	{
		return;
	}
	SecondsSincePublish += DeltaSeconds;
	if (SecondsSincePublish < SimTimePublishIntervalS)
	{
		return;
	}
	SecondsSincePublish = 0.0f;
	if (const UCDSimClockSubsystem* Clock = GetWorld()->GetSubsystem<UCDSimClockSubsystem>())
	{
		ReplicatedSimTimeUs = Clock->GetSimTimeUs();
	}
}
