// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Net/CDSimPlayerState.h"

#include "Net/UnrealNetwork.h"

void ACDSimPlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ACDSimPlayerState, TraineeId);
	DOREPLIFETIME(ACDSimPlayerState, VehicleId);
}
