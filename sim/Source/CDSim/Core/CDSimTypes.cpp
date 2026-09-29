// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md

#include "Core/CDSimTypes.h"

#include "Dom/JsonObject.h"
#include "Misc/DateTime.h"
#include "Misc/Guid.h"

TSharedRef<FJsonObject> FCDSimHeader::ToProtoJson() const
{
	TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetStringField(TEXT("simTimeUs"), FString::Printf(TEXT("%lld"), SimTimeUs));
	Json->SetStringField(TEXT("wallTimeUs"), FString::Printf(TEXT("%lld"), WallTimeUs));
	Json->SetStringField(TEXT("sessionId"), SessionId);
	Json->SetStringField(TEXT("actorId"), ActorId);
	Json->SetStringField(TEXT("source"), CDSimTypes::SourceToProtoName(Source));
	Json->SetStringField(TEXT("seq"), FString::Printf(TEXT("%lld"), Seq));
	return Json;
}

namespace CDSimTypes
{
	FString SourceToProtoName(ECDSimSource Source)
	{
		switch (Source)
		{
		case ECDSimSource::SimClient:
			return TEXT("SOURCE_SIM_CLIENT");
		case ECDSimSource::SimServer:
			return TEXT("SOURCE_SIM_SERVER");
		case ECDSimSource::Autopilot:
			return TEXT("SOURCE_AUTOPILOT");
		case ECDSimSource::Instructor:
			return TEXT("SOURCE_INSTRUCTOR");
		case ECDSimSource::Assessment:
			return TEXT("SOURCE_ASSESSMENT");
		case ECDSimSource::Scenario:
			return TEXT("SOURCE_SCENARIO");
		case ECDSimSource::RL:
			return TEXT("SOURCE_RL");
		case ECDSimSource::Audio:
			return TEXT("SOURCE_AUDIO");
		case ECDSimSource::Unspecified:
		default:
			return TEXT("SOURCE_UNSPECIFIED");
		}
	}

	FString StimulusKindToProtoName(ECDSimStimulusKind Kind)
	{
		switch (Kind)
		{
		case ECDSimStimulusKind::InstructorInject:
			return TEXT("KIND_INSTRUCTOR_INJECT");
		case ECDSimStimulusKind::SystemFailure:
			return TEXT("KIND_SYSTEM_FAILURE");
		case ECDSimStimulusKind::TargetAppearance:
			return TEXT("KIND_TARGET_APPEARANCE");
		case ECDSimStimulusKind::Alarm:
			return TEXT("KIND_ALARM");
		case ECDSimStimulusKind::Unspecified:
		default:
			return TEXT("KIND_UNSPECIFIED");
		}
	}

	FString ResponseKindToProtoName(ECDSimResponseKind Kind)
	{
		switch (Kind)
		{
		case ECDSimResponseKind::ControlInput:
			return TEXT("KIND_CONTROL_INPUT");
		case ECDSimResponseKind::ModeChange:
			return TEXT("KIND_MODE_CHANGE");
		case ECDSimResponseKind::VoiceCommand:
			return TEXT("KIND_VOICE_COMMAND");
		case ECDSimResponseKind::MenuAction:
			return TEXT("KIND_MENU_ACTION");
		case ECDSimResponseKind::Unspecified:
		default:
			return TEXT("KIND_UNSPECIFIED");
		}
	}

	int64 WallTimeNowUs()
	{
		// FDateTime ticks are 100 ns units since 0001-01-01.
		const FDateTime Now = FDateTime::UtcNow();
		const FDateTime UnixEpoch(1970, 1, 1);
		return (Now.GetTicks() - UnixEpoch.GetTicks()) / 10;
	}

	FString NewUuidString()
	{
		return FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens).ToLower();
	}
} // namespace CDSimTypes
