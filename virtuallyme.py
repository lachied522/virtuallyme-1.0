import requests
import json
import openai

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

##openai api key
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY 

def turbo_openai_call(messages, max_tokens, temperature, presence_penalty):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return response["choices"][0]["message"]["content"]


def openai_call(prompt, max_tokens, temperature, presence_penalty):
    try:
        model='text-davinci-003'
        response = openai.Completion.create(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            presence_penalty=presence_penalty,
            stop=[" Me", " AI:"]
        )
        print(model)
    except:
        model='text-davinci-002'
        response = openai.Completion.create(
            model=model,
            prompt=prompt,
            max_tokens=temperature,
            temperature=temperature,
            presence_penalty=presence_penalty,
            stop=[" Me", " AI:"]
        )
        print(model)
    response_text = response.choices[0].text.strip()
    return response_text

def rank_samples(search_string, samples):
    """
    sort samples by how frequently common words appear, only consider words >3 characters
    
    :param search_string: 
    :param samples: array of strings to search through
    """
    if len(samples)==0:
        return []
    else:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(samples)
        search_tfidf = vectorizer.transform(search_string.split())
        cosine_similarities = cosine_similarity(search_tfidf, tfidf_matrix).flatten()

        return cosine_similarities

def construct_messages(user, samples, maxlength, current_prompt):
    """
    construct messages from user data
    :param user: User object instance
    :param job_id: 
    :param maxLength: max length for prompt
    :current_prompt: current prompt to rank samples by
    """
    about = ""
    #about = user.about or ""
    description = ""
    #description = user.description or ""

    messages = []
    length = 0 #approxime length of prompt
    role = "You have adopted a persona. I will ask you to write something. You must provide responses that are consistent with your persona in its idiolect, structure, syntax, word choices, reasoning, and rationale."
    if about != "":
        role += f"\nHere is some information about me: {about}"
    if description != "":
        role += f"\nHere is a description of my writing style: {description}"

    messages.append({"role": "system", "content": role})
    length += len(role.split())

    cosine_similarities = rank_samples(current_prompt, [d["completion"] for d in samples])
    ranked_samples = [item for index, item in sorted(enumerate(samples), key = lambda x: cosine_similarities[x[0]], reverse=True)]
    for prompt_completion in [d for d in ranked_samples if d["feedback"]!="negative"]:
        if length+len(prompt_completion["completion"].split())+len(prompt_completion["prompt"].split()) > maxlength:
            ##prompt limit 3097 tokens (4097-1000 for completion)
            ##1000 tokens ~ 750 words
            break
        else:
            messages.append({"role": "assistant", "content": prompt_completion["completion"]})
            messages.append({"role": "user", "content": prompt_completion["prompt"]})
            length += len(prompt_completion["prompt"].split())+len(prompt_completion["completion"].split())
    #reverse order of messages so most relevant samples appear down the bottom
    return messages[::-1]

def search_web(query):
    url = "http://virtuallyme-websearch:10000"
    headers = {"content-type": "application/json"}
    data = {"query": query}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return json.loads(response.text)

def sort_samples(samples):
    return list(dict.fromkeys(sorted(samples,key=len,reverse=True)))

def detect_gpt(text):
    url = "https://api.gptzero.me/v2/predict/text"
    headers = {"content-type": "application/json"}
    data = {"document": text}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    response_dict = json.loads(response.text)
    return (1 - response_dict["documents"][0]["completely_generated_prob"])*100