// Copyright (c) 2026 Chakravyuha Dynamics Private Limited. Proprietary and confidential.
// UNVERIFIED BUILD — not yet compiled; see docs/BUILDING_UE5.md
//
// Small, forgiving readers for the JSON exported from platform.yaml / area.yaml.
// Missing keys return the supplied default; schema validation already
// happened upstream (`make schemas`), so the engine does not re-validate.

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace CDSimJson
{
	inline TSharedPtr<FJsonObject> ParseObject(const FString& Text)
	{
		TSharedPtr<FJsonObject> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			return nullptr;
		}
		return Root;
	}

	inline TSharedPtr<FJsonObject> Object(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key)
	{
		const TSharedPtr<FJsonObject>* Out = nullptr;
		if (Obj.IsValid() && Obj->TryGetObjectField(Key, Out) && Out != nullptr)
		{
			return *Out;
		}
		return nullptr;
	}

	inline const TArray<TSharedPtr<FJsonValue>>* Array(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key)
	{
		const TArray<TSharedPtr<FJsonValue>>* Out = nullptr;
		if (Obj.IsValid() && Obj->TryGetArrayField(Key, Out))
		{
			return Out;
		}
		return nullptr;
	}

	inline double Number(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key, double Default = 0.0)
	{
		double Out = Default;
		if (Obj.IsValid() && Obj->TryGetNumberField(Key, Out))
		{
			return Out;
		}
		return Default;
	}

	inline FString String(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key, const FString& Default = FString())
	{
		FString Out;
		if (Obj.IsValid() && Obj->TryGetStringField(Key, Out))
		{
			return Out;
		}
		return Default;
	}

	inline bool Bool(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key, bool Default = false)
	{
		bool Out = Default;
		if (Obj.IsValid() && Obj->TryGetBoolField(Key, Out))
		{
			return Out;
		}
		return Default;
	}

	/** Reads a JSON array of 3 numbers, e.g. position_m: [x, y, z]. */
	inline FVector Vector3(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Key, const FVector& Default = FVector::ZeroVector)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = Array(Obj, Key);
		if (Values == nullptr || Values->Num() != 3)
		{
			return Default;
		}
		return FVector((*Values)[0]->AsNumber(), (*Values)[1]->AsNumber(), (*Values)[2]->AsNumber());
	}

	/** Every numeric member of an object as Name -> float (e.g. sensor noise / params blocks). */
	inline TMap<FName, float> NumberMap(const TSharedPtr<FJsonObject>& Obj)
	{
		TMap<FName, float> Out;
		if (!Obj.IsValid())
		{
			return Out;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Obj->Values)
		{
			double Value = 0.0;
			if (Pair.Value.IsValid() && Pair.Value->TryGetNumber(Value))
			{
				Out.Add(FName(*Pair.Key), static_cast<float>(Value));
			}
		}
		return Out;
	}

	inline bool LoadFile(const FString& Path, TSharedPtr<FJsonObject>& OutRoot, FString& OutError)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			OutError = FString::Printf(TEXT("cannot read %s (run scripts/ue5/export_platform_json.py)"), *Path);
			return false;
		}
		OutRoot = ParseObject(Text);
		if (!OutRoot.IsValid())
		{
			OutError = FString::Printf(TEXT("invalid JSON in %s"), *Path);
			return false;
		}
		return true;
	}
} // namespace CDSimJson
