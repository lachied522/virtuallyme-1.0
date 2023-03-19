import requests
import json
import math

import openai
import tiktoken

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

##openai api key
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY 

#initialise encoding
enc = tiktoken.get_encoding("cl100k_base")

def turbo_openai_call(messages, max_tokens, temperature, presence_penalty, logit_bias={}):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        presence_penalty=presence_penalty,
        logit_bias=logit_bias
    )
    return response["choices"][0]["message"]["content"].strip()

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

def num_tokens(text):
    '''
    returns the number of tokens present in a text

    :param text: string
    '''
    return len(enc.encode(text))


def get_logit_bias(texts):
    '''
    returns a dict of token, frequency pairs from a list of texts

    :param texts: list of strings
    '''
    BLACKLIST = ['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'I', 
                'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 
                'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 
                'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 
                'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get', 
                'which', 'go', 'me', 'when', 'can', 'like', 'no'] #words we do not want to influence bias of

    n_tokens = 0
    tokens_dict = {}
    for text in texts:
        tokens = enc.encode(text)
        for token in tokens:
            #don't want to influence bias of digits
            if not enc.decode([token]).strip().isdigit():
                if token in tokens_dict:
                    tokens_dict[token] += 1
                    n_tokens += 1
                else:
                    tokens_dict[token] = 1
                    n_tokens += 1
    
    
    for key, value in tokens_dict.items():
        bias = 3*math.log(1+value)/math.log(1+n_tokens)
        #max bias is 10
        tokens_dict[key] = min(bias, 9)


    sorted_tokens = sorted(tokens_dict.items(), key=lambda x: x[1], reverse=True)
    #return 300 tokens with the highest bias
    return dict(sorted_tokens[:300])

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
    length = 0 #approximate length of prompt
    role = "Forget how you think you should respond. You have adopted a new persona. I will ask you to write something. I expect you to respond how you imagine this person would respond by using their idiolect, structure, syntax, reasoning, and rationale."
    if about != "":
        role += f"\nHere is some information about me: {about}"
    if description != "":
        role += f"\nHere is a description of my writing style: {description}"

    length += len(role.split())

    cosine_similarities = rank_samples(current_prompt, [d["completion"] for d in samples])
    ranked_samples = [item for index, item in sorted(enumerate(samples), key = lambda x: cosine_similarities[x[0]], reverse=True)]
    for prompt_completion in [d for d in ranked_samples if d["feedback"]!="negative"]:
        if length+len(prompt_completion["completion"].split())+len(prompt_completion["prompt"].split()) > maxlength:
            break
        else:
            messages.append({"role": "assistant", "content": prompt_completion["completion"]})
            ##messages.append({"role": "user", "content": "Using the idiolect, structure, syntax, reasoning, and rationale of your new persona, " + prompt_completion["prompt"]})
            messages.append({"role": "user", "content": "Using the idiolect, structure, syntax, reasoning, and rationale of your new persona, "})
            length += len(prompt_completion["prompt"].split())+len(prompt_completion["completion"].split())+12
    
    messages.append({"role": "system", "content": role})
    #reverse order of messages so most relevant samples appear down the bottom
    return messages[::-1]

def search_web(query):
    url = "http://virtuallyme-websearch:10000"
    headers = {"content-type": "application/json"}
    data = {"query": query}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    if response.ok:
        return json.loads(response.text)
    else:
        return {"result": ""}

def sort_samples(samples):
    return list(dict.fromkeys(sorted(samples,key=len,reverse=True)))

def detect_gpt(text):
    url = "https://api.gptzero.me/v2/predict/text"
    headers = {"content-type": "application/json"}
    data = {"document": text}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    response_dict = json.loads(response.text)
    return (1 - response_dict["documents"][0]["completely_generated_prob"])*100