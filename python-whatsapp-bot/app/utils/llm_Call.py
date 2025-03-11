# import openai 

# client = openai.OpenAI(api_key="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")

# response = client.chat.completions.create(
#     model="gpt-4o-mini",
#     messages=[{"role": "user", "content": "Hello, how are you?"}]
# )

# print(response)

import openai

client = openai.OpenAI(api_key="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")

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about OpenAI."}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
