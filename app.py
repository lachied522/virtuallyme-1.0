from flask import Flask, Response, request
from flask_sqlalchemy import SQLAlchemy

import json

from database import DATABASE_URL

from virtuallyme import *


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.String(100), primary_key=True) #get from Memberstack
    name = db.Column(db.String(100))
    monthly_words = db.Column(db.Integer)
    description = db.Column(db.Text)
    jobs = db.relationship('Job', backref='user', lazy='joined')
    tasks = db.relationship('Task', backref='user', lazy='joined')

    def __repr__(self):
        return f'<User "{self.id}">'


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    word_count = db.Column(db.Integer)
    data = db.relationship('Data', backref='job', lazy='joined')
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<Job "{self.name}">'
    
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.Text)
    completion = db.Column(db.Text)
    category = db.Column(db.String(100)) #task, idea, or rewrite
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'))
    
class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.Text)
    completion = db.Column(db.Text)
    feedback = db.Column(db.String(100)) #user-upload, positive, or negative
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))


@app.route("/create_user", methods=["POST"])
def create_user():
    user = User(id = request.json["member_id"], name = request.json["name"], monthly_words = 0)
    db.session.add(user)
    db.session.commit()
    return Response(status=200)

@app.route("/get_user", methods=["GET"])
def get_user():
    #format data to return to user on page load
    user = User.query.get(request.headers["user"])
    
    user_jobs = []
    
    for job in user.jobs:
        job_samples = [{"prompt": d.prompt, "completion": d.completion} for d in job.data if d.feedback=="user-upload"]
        user_jobs.append({"name": job.name, "word_count": job.word_count, "data": job_samples})

    user_tasks = [{"prompt": task.prompt, "completion": task.completion} for task in user.tasks if task.category=="task"]
    user_ideas = [{"prompt": task.prompt, "completion": task.completion} for task in user.tasks if task.category=="idea"]

    response_dict = {
        "user": user_jobs,
        "tasks": user_tasks[::-1],
        "ideas": user_ideas[::-1]
    }

    return Response(json.dumps(response_dict), status=200)


@app.route("/create_job", methods=["POST"])
def create_job():
    user = User.query.get(request.json["member_id"])
    job = Job(name=request.json["job_name"], word_count=0, user_id=user.id)
    db.session.add(job)
    db.session.commit()
    return Response(status=200)

@app.route("/sync_job", methods=["POST"])
def sync_job():
    #receives job data as list of dict objects with prompt, completion key
    user = User.query.get(request.json["member_id"])
    job = Job.query.get(request.json["job_id"])
    
    new_data = request.json["data"]
    #delete existing data belonging to job
    for data in [d for d in job.data if d.feedback=="user-upload"]:
        db.session.delete(data)
    
    for prompt_completion in new_data:
        prompt = prompt_completion["prompt"]
        completion = prompt_completion["completion"]
        db.session.add(Data(prompt=prompt, completion=completion, feedback="user-upload", job_id=job.id))

    #run description if number of words is at least 300
    #if a new sample substantially changes the sum of samples
    new_samples = [d["completion"] for d in new_data]
    existing_samples = [d["completion"] for job in user.jobs for d in job.data]
    
    all_samples = new_samples + existing_samples
    all_samples_str = str("\n".join(rank_samples(all_samples)))[:8000]
    existing_samples_str = str("\n".join(rank_samples(existing_samples)))[:8000]

    #only consider first 8,000 characters ~ 2000 words
    if len(all_samples_str.split()) > 300 and all_samples_str==existing_samples_str:
        prompt = f"Pretend the following text was written by you.\nText: {all_samples_str}\nUsing a minimum of 100 words, give an elaborate description of your writing style, including a description of your audience, semantics, syntax, and sentence structure. Speak in first person."
        description = openai_call(prompt, 500, 0.4, 0.3)
        #update user description
        user.description = description

        #pass decsription to Zapier
        url = "https://hooks.zapier.com/hooks/catch/14316057/bvhzkww/"
        response_dictionary = {
            "webflow_member_ID": user.id,
            "description": description
        }

        response_json = json.dumps(response_dictionary)

        response = requests.post(url, data=response_json)

    db.session.commit()
    return Response(status=200)

@app.route("/handle_task", methods=["GET", "POST"])
def handle_task():
    user = User.query.get(request.json["member_id"])

    category = request.json["type"]
    topic = request.json["topic"]
    additional = request.json["type"]

    if request.json["search"]:
        search_result = search_web(topic)
    else:
        search_result = {"result": ""}

    if request.json["job_id"] == -1:
        #combine all job data
        samples = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback} for job in user.jobs for d in job.data]
    elif request.json["job_id"] > 0:
        job = Job.query.get(request.json["job_id"])
        #get job data
        samples = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback} for d in job.data]
    else:
        #no job data
        samples = []
    
    #construct prompt
    #preliminaries
    
    description = user.description or ""

    prompt = f"You are my writing assistant. You must adapt to my writing style by replicating the nuances of my writing."
    if description != "":
        #if user description exists
        prompt += f" Below is a description of my writing style.\nDescription: {description}"


    
    prompt += "\nMe: "
    for prompt_completion in rank_samples(topic, samples):
        print(len(search_result["result"].split()))
        if len(prompt.split())+len(prompt_completion["completion"].split()) > 2250-len(additional.split())-len(description.split())-len(search_result["result"].split()):
            ##prompt limit 3097 tokens (4097-1000 for completion)
            ##1000 tokens ~ 750 words
            break
        else:
            prompt += prompt_completion["prompt"] + "\nAI: " + prompt_completion["completion"] + "\nMe: "
            if prompt_completion["feedback"]=="negative":
                prompt += "That didn't sound like me. "

    #add current prompt
    if request.json["search"] and search_result["result"] != "":
        context = search_result["result"]
        #if web search was successful, include results in the prompt
        prompt += f"Write a {category} about {topic}. {additional}. You may include the following information: {context}\nAI: "
    else:
        prompt += f"Write a {category} about {topic}. {additional}\nAI: "

    
    response_text = openai_call(prompt, 1000, 0.9, 0.6)

    if request.json["search"] and search_result["result"] != "":
        #if web search was successful, return the url
        response_text += "Source: " + str(search_result["url"])
        

    return json.dumps({"completion": response_text})






if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
    