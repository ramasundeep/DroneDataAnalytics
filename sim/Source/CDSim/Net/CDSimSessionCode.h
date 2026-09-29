// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"

#include "CDSimSessionCode.generated.h"

/**
 * 6-character session codes for joining a fleet session on the LAN
 * (e.g. "K7QM3X"). Alphabet excludes look-alikes (0/O, 1/I/L) so codes can
 * be read aloud across a classroom. 31^6 ~ 887 million codes.
 *
 * Generation / validation is implemented. LAN resolution is not:
 * TODO(Phase 5): server answers a UDP broadcast beacon with its address for
 * a matching code; client then travels to it (docs/10_ROADMAP.md). No
 * internet or matchmaking service is involved (offline-first).
 */
UCLASS()
class CDSIM_API UCDSimSessionCode : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	static constexpr int32 CodeLength = 6;

	/** New random code. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Fleet")
	static FString GenerateSessionCode();

	/** Upper-cases and strips spaces/dashes, e.g. " k7q-m3x " -> "K7QM3X". */
	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	static FString NormaliseSessionCode(const FString& Code);

	/** True if Code (after normalisation) is 6 characters from the alphabet. */
	UFUNCTION(BlueprintPure, Category = "CDSim|Fleet")
	static bool IsValidSessionCode(const FString& Code);

	/**
	 * Find the server hosting Code on the LAN. Not implemented yet: logs and
	 * returns false. TODO(Phase 5).
	 */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Fleet")
	static bool ResolveSessionCodeOnLan(const FString& Code, FString& OutServerAddress);

	static const TCHAR* GetAlphabet();
};
