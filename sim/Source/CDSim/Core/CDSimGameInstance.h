// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"

#include "CDSimGameInstance.generated.h"

/**
 * Session-wide identity and launch options. Parsed once from the command line:
 *
 *   -Platform=<id>        platform id (platforms/<id>/platform.yaml). Default cdpl_quad_01.
 *   -Area=<id>            area id (terrain/areas/<id>/area.yaml). Default flat_test.
 *   -Session=<uuid>       session UUID assigned by the API service. Generated if absent.
 *   -RecorderUrl=<url>    recorder service base URL. Default http://127.0.0.1:8001 (local box).
 *   -SitlPort=<port>      UDP port for the ArduPilot JSON physics backend. Default 9002.
 *   -NoSitl               do not open the SITL binding (visual / replay only).
 *
 * Offline-first: every default points at the local machine; nothing here
 * reaches the internet.
 */
UCLASS()
class CDSIM_API UCDSimGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	virtual void Init() override;

	UFUNCTION(BlueprintPure, Category = "CDSim|Session")
	FString GetSessionId() const { return SessionId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Session")
	FName GetPlatformId() const { return PlatformId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Session")
	FName GetAreaId() const { return AreaId; }

	UFUNCTION(BlueprintPure, Category = "CDSim|Session")
	FString GetRecorderUrl() const { return RecorderUrl; }

	int32 GetSitlPort() const { return SitlPort; }
	bool IsSitlEnabled() const { return bSitlEnabled; }

protected:
	virtual void OnStart() override;

private:
	void ParseCommandLine(const TCHAR* CommandLine);

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Session")
	FString SessionId;

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Session")
	FName PlatformId = TEXT("cdpl_quad_01");

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Session")
	FName AreaId = TEXT("flat_test");

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Session")
	FString RecorderUrl = TEXT("http://127.0.0.1:8001");

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Session")
	int32 SitlPort = 9002;

	UPROPERTY(VisibleInstanceOnly, Category = "CDSim|Session")
	bool bSitlEnabled = true;
};
