import requests
from bs4 import BeautifulSoup

import openai
import asyncio
import aiohttp

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from apiclient.discovery import build

##openai api key
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY 

##google api key
GOOGLE_API_KEY = "AIzaSyCm-gGY014pfYImeiLMqCYuNGQ1nf8g2eg"
GOOGLE_CSE_ID = "d7251a9905c2540fa"

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

async def fetch_page(url, session):
    try:
        async with session.get(url) as response:
                return await response.text()
    except:
        return ""

async def scrape(url, session):
    html = await fetch_page(url, session)
    soup = BeautifulSoup(html, 'html.parser')
    # kill all script and style elements
    for script in soup(["script", "style", "a", "header", "footer", "nav"]):
        script.extract()    # rip it out
    # get text
    text = soup.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines() if len(line)>128)
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    #split text into blocks of 100 words
    n = 100
    return [{"text": " ".join(text.split()[i:i+n]), "url": url} for i in range(0, len(text.split()), n)]

async def conduct_search(query):    
    api_key = "AIzaSyCm-gGY014pfYImeiLMqCYuNGQ1nf8g2eg"
    cse_ID = "d7251a9905c2540fa"

    query += " -headlines -video -pdf"

    resource = build("customsearch", "v1", developerKey=api_key).cse()
    result = resource.list(q=query, cx=cse_ID).execute()

    links = [item["link"] for item in result["items"]][:3]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9", 
        "Referer": "http://www.google.com/"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = []
            for url in links:
                tasks.append(asyncio.ensure_future(scrape(url, session)))
            results = await asyncio.gather(*tasks)
            
            results = [{"text": d["text"], "url": d["url"]} for sublist in results for d in sublist]
            cosine_similarities = rank_samples(query, [d["text"] for d in results])
            ranked_context = [item for index, item in sorted(enumerate(results), key = lambda x: cosine_similarities[x[0]], reverse=True)]
            #get a a bit of context from each url
            joined_context = ""
            urls = []
            for d in ranked_context:
                url = d["url"]
                if urls.count(url) < 2:
                    if len(joined_context) > 8000:
                        #max length 8000 characters ~ 2000 words
                        break
                    else:
                        joined_context += d["text"]
                        urls.append(url)
            message = [{
                "role": "user", 
                "content": f"I would like to write about {query}. Summarise the relevant points from the following text:\n{joined_context}"
            }]
            completion = turbo_openai_call(message, 500, 0.4, 0.4)
            return {"result": completion, "urls": list(set(urls))}
    except:
        return {"result": "", "urls": []}

def search_web(query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(conduct_search(query))

def sort_samples(samples):
    return list(dict.fromkeys(sorted(samples,key=len,reverse=True)))
