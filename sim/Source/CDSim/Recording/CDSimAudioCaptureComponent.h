// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"

#include "CDSimAudioCaptureComponent.generated.h"

/**
 * Trainee voice capture (docs/ADR/0013): UE5 capture -> Opus chunks stamped
 * with sim time -> recorder -> MinIO, subject to consent and retention.
 *
 * CONSENT FIRST: StartCapture() refuses to run unless SetConsent(true) has
 * been called for this trainee in this session (the consent record itself is
 * owned by the API service). Revoking consent stops capture immediately.
 *
 * Skeleton only. TODO(Phase 3): microphone capture (AudioCapture module),
 * 20 ms Opus frames batched into ~1 s cdsim.v1.AudioChunk messages with
 * header.simTimeUs = time of the first sample, upload via the recorder
 * (docs/10_ROADMAP.md). Until then StartCapture() logs and returns false.
 */
UCLASS(ClassGroup = (CDSim), meta = (BlueprintSpawnableComponent))
class CDSIM_API UCDSimAudioCaptureComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCDSimAudioCaptureComponent();

	/** Record the trainee's consent decision for this session. false stops any capture. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Audio")
	void SetConsent(const FString& InTraineeId, bool bInConsentGiven);

	UFUNCTION(BlueprintPure, Category = "CDSim|Audio")
	bool HasConsent() const { return bConsentGiven; }

	/** Begin capturing. Returns false if there is no consent or capture is unavailable. */
	UFUNCTION(BlueprintCallable, Category = "CDSim|Audio")
	bool StartCapture();

	UFUNCTION(BlueprintCallable, Category = "CDSim|Audio")
	void StopCapture();

	UFUNCTION(BlueprintPure, Category = "CDSim|Audio")
	bool IsCapturing() const { return bCapturing; }

protected:
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(EditAnywhere, Category = "CDSim|Audio")
	int32 SampleRateHz = 48000;

	UPROPERTY(EditAnywhere, Category = "CDSim|Audio")
	int32 Channels = 1;

private:
	FString TraineeId;
	bool bConsentGiven = false;
	bool bCapturing = false;
};
