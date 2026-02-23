#!/usr/bin/env python3

import yaml
from openai import OpenAI

def main():
    # Path to your YAML file
    yaml_path = "/home/mbzirc2/catkin_ws/src/coral_inspection/config/openai_keys.yaml"

    # Load API key
    try:
        with open(yaml_path, "r") as f:
            cfg = yaml.safe_load(f)

        api_key = cfg["openai"]["api_key"]
        model   = cfg["openai"].get("model_name", "gpt-4.1")
        temp    = cfg["openai"].get("temperature", 0.2)
        max_tk  = cfg["openai"].get("max_tokens", 200)
    except Exception as e:
        print("❌ Failed to read YAML config:", e)
        return

    print("Loaded API key and model from YAML:")
    print("  model =", model)
    print("  temperature =", temp)
    print("  max_tokens =", max_tk)

    # Test the API call
    try:
        client = OpenAI(api_key=api_key)

        resp = client.chat.completions.create(
            model=model,
            temperature=temp,
            max_tokens=max_tk,
            messages=[
                {"role": "system", "content": "You are a test system checking OpenAI connectivity."},
                {"role": "user", "content": "Say hello from the coral inspection robot simulation."}
            ]
        )

        print("\n✅ API call SUCCESSFUL!")
        print("Model response:")
        print(resp.choices[0].message.content)

    except Exception as e:
        print("\n❌ API call FAILED:", e)

if __name__ == "__main__":
    main()
