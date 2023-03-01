import json
import requests
from bs4 import BeautifulSoup

import openai

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from apiclient.discovery import build



##openai api key
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY 

##google api key
GOOGLE_API_KEY = "AIzaSyCm-gGY014pfYImeiLMqCYuNGQ1nf8g2eg"
GOOGLE_CSE_ID = "d7251a9905c2540fa"

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


def sum_webpage(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9", 
        "Referer": "http://www.google.com/"
    }
    html = requests.get(url, headers=headers)
    soup = BeautifulSoup(html.text, features="html.parser")

    # kill all script and style elements
    for script in soup(["script", "style", "a", "header", "footer", "nav"]):
        script.extract()    # rip it out

    # get text
    text = soup.get_text()

    # break into lines and remove leading and trailing space on each
    # only include lines greater than 24 characters long (indicates body text)
    lines = (line.strip() for line in text.splitlines() if len(line) > 24)
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    # include first 10000 characters ~ 2500 tokens
    text = '\n'.join(chunk for chunk in chunks if chunk)[:8000]

    # only pass prompt to OpenAI if webpage actually returned something
    # check if text is at least 100 words long
    if len(text.split()) > 100:
        prompt = f"Summarise the key points of the following text:\n{text}"
        return openai_call(prompt, 500, 0.4, 0.6)
    else:
        return ""

def search_web(query):
    resource = build("customsearch", "v1", developerKey=GOOGLE_API_KEY).cse()
    query += " -headlines -video"

    result = resource.list(q=query, cx=GOOGLE_CSE_ID).execute()

    #want to select first search result which has content in the body
    #select first url containing a slug longer than 12 characters
    url = None
    for item in result["items"]:
        slug = [s for s in item["link"].split("/") if s!=""][-1]
        if len(slug) > 12:
            url = item["link"]
            search_result = sum_webpage(url)
            break
    if url:
        return {"result": search_result, "url": url}
    else:
        return {"result": ""}
    
def rank_samples(prompt, samples):
    """
    sort samples by how frequently common words appear, only consider words >3 characters
    
    :param prompt: string to run ranking on
    :param samples: list of dicts containing prompt, completion pairs
    """
    #vectorizer = TfidfVectorizer()
    #tfidf_matrix = vectorizer.fit_transform([s for s in samples[i]["prompt"].split() if len(s) > 3])
    #prompt_tfidf = vectorizer.transform([prompt])
    #cosine_similarities = cosine_similarity(prompt_tfidf, tfidf_matrix).flatten()
    if len(samples)==0:
        return []
    else:
        word_counts = {}
        prompt_words = [s for s in prompt.split() if len(s) > 3]
        for i in range(len(samples)):
            count = 0
            for word in prompt_words:
                if word in [s for s in samples[i]["prompt"].split() if len(s) > 3]:
                    count += 1
            word_counts[i] = count
        
        return [item for index, item in sorted(enumerate(samples), key = lambda x: word_counts[x[0]], reverse=True)]
    

def sort_samples(samples):
    return list(dict.fromkeys(sorted(samples,key=len,reverse=True)))
