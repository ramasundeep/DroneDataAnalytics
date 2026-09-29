// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "XR/CDSimXRSettings.h"

#include "CDSim.h"
#include "HAL/IConsoleManager.h"
#include "HeadMountedDisplayFunctionLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

const TCHAR* UCDSimXRSettings::CVarName = TEXT("cdsim.XR.Enable");

static TAutoConsoleVariable<bool> CVarCDSimXREnable(TEXT("cdsim.XR.Enable"), false,
	TEXT("CD Sim VR configuration. 0 = desktop (default), 1 = VR via OpenXR. Also set by -vr. See docs/BUILDING_UE5.md."),
	ECVF_Default);

bool UCDSimXRSettings::IsXREnabled()
{
	return CVarCDSimXREnable.GetValueOnGameThread();
}

void UCDSimXRSettings::ApplyStartupXRMode()
{
	if (IsRunningDedicatedServer())
	{
		return; // Servers never render.
	}

	if (FParse::Param(FCommandLine::Get(), TEXT("vr")))
	{
		CVarCDSimXREnable->Set(true, ECVF_SetByCommandline);
	}

	const bool bWantXR = IsXREnabled();
	const bool bHmdOn = UHeadMountedDisplayFunctionLibrary::IsHeadMountedDisplayEnabled();
	if (bWantXR && !bHmdOn)
	{
		const bool bOk = UHeadMountedDisplayFunctionLibrary::EnableHMD(true);
		UE_LOG(LogCDSim, Log, TEXT("XR: VR configuration requested; EnableHMD(true) %s."),
			bOk ? TEXT("succeeded") : TEXT("FAILED (is an OpenXR runtime installed and a headset connected?)"));
	}
	else if (!bWantXR && bHmdOn)
	{
		UHeadMountedDisplayFunctionLibrary::EnableHMD(false);
		UE_LOG(LogCDSim, Log, TEXT("XR: desktop configuration; HMD disabled."));
	}
	else
	{
		UE_LOG(LogCDSim, Log, TEXT("XR: %s configuration."), bWantXR ? TEXT("VR") : TEXT("desktop"));
	}
}
