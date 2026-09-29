// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Shared value types mirroring schemas/common.proto and schemas/events.proto.
// The proto files are the contract (CLAUDE.md "Schemas first"); if a field or
// enum value changes there, change it here and in
// services/common/src/cdsim_common/events.py in the same PR.

#pragma once

#include "CoreMinimal.h"

#include "CDSimTypes.generated.h"

class FJsonObject;

/** Mirrors cdsim.v1.Source (schemas/common.proto). Numeric values match the proto. */
UENUM(BlueprintType)
enum class ECDSimSource : uint8
{
	Unspecified = 0 UMETA(DisplayName = "SOURCE_UNSPECIFIED"),
	SimClient = 1 UMETA(DisplayName = "SOURCE_SIM_CLIENT"),
	SimServer = 2 UMETA(DisplayName = "SOURCE_SIM_SERVER"),
	Autopilot = 3 UMETA(DisplayName = "SOURCE_AUTOPILOT"),
	Instructor = 4 UMETA(DisplayName = "SOURCE_INSTRUCTOR"),
	Assessment = 5 UMETA(DisplayName = "SOURCE_ASSESSMENT"),
	Scenario = 6 UMETA(DisplayName = "SOURCE_SCENARIO"),
	RL = 7 UMETA(DisplayName = "SOURCE_RL"),
	Audio = 8 UMETA(DisplayName = "SOURCE_AUDIO"),
};

/** Mirrors cdsim.v1.Stimulus.Kind (schemas/events.proto). */
UENUM(BlueprintType)
enum class ECDSimStimulusKind : uint8
{
	Unspecified = 0,
	InstructorInject = 1,
	SystemFailure = 2,
	TargetAppearance = 3,
	Alarm = 4,
};

/** Mirrors cdsim.v1.Response.Kind (schemas/events.proto). */
UENUM(BlueprintType)
enum class ECDSimResponseKind : uint8
{
	Unspecified = 0,
	ControlInput = 1,
	ModeChange = 2,
	VoiceCommand = 3,
	MenuAction = 4,
};

/**
 * Mirrors cdsim.v1.Header: the envelope stamped on every recorded datum.
 * SimTimeUs is THE ordering key; WallTimeUs is reference only (CLAUDE.md "Time").
 */
USTRUCT(BlueprintType)
struct CDSIM_API FCDSimHeader
{
	GENERATED_BODY()

	/** Monotonic simulation time in microseconds since session start. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Header")
	int64 SimTimeUs = 0;

	/** Producer wall-clock, Unix epoch microseconds. Reference only. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Header")
	int64 WallTimeUs = 0;

	/** Session UUID (string form). */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Header")
	FString SessionId;

	/** Trainee id, vehicle id, "instructor" or "system". */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Header")
	FString ActorId;

	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Header")
	ECDSimSource Source = ECDSimSource::Unspecified;

	/** Producer-local sequence number. Proto type is uint64; always >= 0 here. */
	UPROPERTY(BlueprintReadOnly, Category = "CDSim|Header")
	int64 Seq = 0;

	/**
	 * Serialise using the protobuf JSON mapping with the field names used by
	 * cdsim_common.events.Header aliases: simTimeUs, wallTimeUs, sessionId,
	 * actorId, source, seq. 64-bit integers are written as JSON strings, which
	 * is the canonical proto3 JSON form and avoids double precision loss.
	 */
	TSharedRef<FJsonObject> ToProtoJson() const;
};

namespace CDSimTypes
{
	/** Proto enum value name, e.g. "SOURCE_SIM_CLIENT". */
	CDSIM_API FString SourceToProtoName(ECDSimSource Source);
	/** Proto enum value name, e.g. "KIND_SYSTEM_FAILURE". */
	CDSIM_API FString StimulusKindToProtoName(ECDSimStimulusKind Kind);
	/** Proto enum value name, e.g. "KIND_CONTROL_INPUT". */
	CDSIM_API FString ResponseKindToProtoName(ECDSimResponseKind Kind);

	/** Current wall-clock as Unix epoch microseconds (reference only). */
	CDSIM_API int64 WallTimeNowUs();

	/** New lowercase hyphenated UUID, matching Python's str(uuid.uuid4()) shape. */
	CDSIM_API FString NewUuidString();
} // namespace CDSimTypes
