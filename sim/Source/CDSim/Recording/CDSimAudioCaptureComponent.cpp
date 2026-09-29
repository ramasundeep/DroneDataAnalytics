// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Recording/CDSimAudioCaptureComponent.h"

#include "CDSim.h"

UCDSimAudioCaptureComponent::UCDSimAudioCaptureComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UCDSimAudioCaptureComponent::SetConsent(const FString& InTraineeId, bool bInConsentGiven)
{
	TraineeId = InTraineeId;
	bConsentGiven = bInConsentGiven;
	if (!bConsentGiven && bCapturing)
	{
		StopCapture();
	}
}

bool UCDSimAudioCaptureComponent::StartCapture()
{
	if (!bConsentGiven)
	{
		UE_LOG(LogCDSim, Warning, TEXT("Audio: capture refused for trainee '%s' - no consent recorded."), *TraineeId);
		return false;
	}
	// TODO(Phase 3): open the default capture device, encode Opus, stamp with sim time (docs/ADR/0013).
	UE_LOG(LogCDSim, Warning, TEXT("Audio: capture not implemented yet (Phase 3, docs/10_ROADMAP.md)."));
	return false;
}

void UCDSimAudioCaptureComponent::StopCapture()
{
	bCapturing = false;
}

void UCDSimAudioCaptureComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	StopCapture();
	Super::EndPlay(EndPlayReason);
}
