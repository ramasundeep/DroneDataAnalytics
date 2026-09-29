// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Core/CDSimGameInstance.h"

#include "CDSim.h"
#include "Core/CDSimTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "XR/CDSimXRSettings.h"

void UCDSimGameInstance::Init()
{
	Super::Init();
	ParseCommandLine(FCommandLine::Get());
	UE_LOG(LogCDSim, Log, TEXT("Session %s: platform=%s area=%s recorder=%s sitl=%s:%d"), *SessionId,
		*PlatformId.ToString(), *AreaId.ToString(), *RecorderUrl, bSitlEnabled ? TEXT("on") : TEXT("off"),
		SitlPort);
}

void UCDSimGameInstance::OnStart()
{
	Super::OnStart();
	// Desktop unless -vr / cdsim.XR.Enable=1. VR is a configuration, not a fork.
	UCDSimXRSettings::ApplyStartupXRMode();
}

void UCDSimGameInstance::ParseCommandLine(const TCHAR* CommandLine)
{
	// NOTE: FParse::Value matches "Key=" anywhere in the command line.
	FString Value;
	if (FParse::Value(CommandLine, TEXT("Platform="), Value) && !Value.IsEmpty())
	{
		PlatformId = FName(*Value);
	}
	if (FParse::Value(CommandLine, TEXT("Area="), Value) && !Value.IsEmpty())
	{
		AreaId = FName(*Value);
	}
	if (FParse::Value(CommandLine, TEXT("Session="), Value) && !Value.IsEmpty())
	{
		SessionId = Value.ToLower();
	}
	else
	{
		// Standalone / PIE runs without the API service still need a session id
		// so the recorder can file their data.
		SessionId = CDSimTypes::NewUuidString();
		UE_LOG(LogCDSim, Log, TEXT("No -Session= given; generated %s."), *SessionId);
	}
	if (FParse::Value(CommandLine, TEXT("RecorderUrl="), Value) && !Value.IsEmpty())
	{
		RecorderUrl = Value;
	}
	int32 Port = 0;
	if (FParse::Value(CommandLine, TEXT("SitlPort="), Port) && Port > 0 && Port < 65536)
	{
		SitlPort = Port;
	}
	if (FParse::Param(CommandLine, TEXT("NoSitl")))
	{
		bSitlEnabled = false;
	}
}
