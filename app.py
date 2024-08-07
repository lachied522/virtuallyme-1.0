from flask import Flask, Response, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import URLType
from flask_cors import CORS

import json
import uuid
from datetime import datetime

from docx import Document
from pdfreader import SimplePDFViewer

from virtuallyme import *

from database import DATABASE_URL

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

class User(db.Model):
    id = db.Column(db.String(100), primary_key=True) #get from Memberstack
    name = db.Column(db.String(100))
    about = db.Column(db.Text)
    description = db.Column(db.Text)
    monthly_words = db.Column(db.Integer)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow())
    sources = db.relationship('Source', backref='sources', lazy='joined')
    feedback = db.Column(db.String(10)) #positive or negative
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'))

class Source(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(URLType())
    display = db.Column(URLType())
    title = db.Column(db.String())
    preview = db.Column(db.Text())
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
    
class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.Text)
    completion = db.Column(db.Text)
    feedback = db.Column(db.String(100)) #user-upload, positive, or negative
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'member_id, Access-Control-Allow-Headers, Access-Control-Request-Headers, Origin, Accept, Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route("/javascript", methods=["GET"])
def serve_js():
    return send_from_directory(".", "javascript_copy.js")

@app.route("/create_user", methods=["POST"])
def create_user():
    """
    Called when a user signs up. Creates empty user object in DB.

    :param member_id: user's Memberstack ID
    :param name: user's first name    
    """
    user = User(id = request.json["member_id"], name = request.json["name"], monthly_words = 0)
    db.session.add(user)
    db.session.commit()
    return Response(status=200)

@app.route("/get_user", methods=["GET"])
def get_user():
    """
    Called when the page loads. Retrieves stored samples and previous task data.

    :param member_id: user's Memberstack ID
    """
    user = User.query.get(request.headers.get("member_id"))

    try:
        user_jobs = []
        for job in user.jobs:
            job_samples = [{"prompt": d.prompt, "completion": d.completion} for d in job.data if d.feedback=="user-upload"]
            user_jobs.append({"job_id": job.id, "name": job.name, "word_count": job.word_count, "data": job_samples})
        
        all_tasks = Task.query.filter_by(user_id=request.headers.get("member_id")).order_by(Task.created_at).all()
        user_tasks = []
        for task in [d for d in all_tasks if d.category=="task"]:
            sources = [{"url": d.url, "display": d.display, "title": d.title, "preview": d.preview} for d in task.sources]
            user_tasks.append({"prompt": task.prompt, "completion": task.completion, "feedback": task.feedback, "created": str(task.created_at), "sources": sources})

        user_ideas = [{"prompt": d.prompt, "completion": d.completion, "created": str(task.created_at)} for d in all_tasks if d.category=="idea"]
        user_rewrites = [{"prompt": d.prompt, "completion": d.completion, "created": str(task.created_at)} for d in all_tasks if d.category=="rewrite"]
    except Exception as e:
        print(e)
        user_jobs = []
        user_tasks = []
        user_idea = []
        user_rewrites = []
        #user has not been created
        user = User(id=request.headers.get("member_id"), monthly_words=0)
        db.session.add(user)
        db.session.commit()

    response_dict = {
        "description": user.description or "",
        "about": user.about or "",
        "words": user.monthly_words or 0,
        "user": user_jobs,
        "tasks": user_tasks,
        "ideas": user_ideas,
        "rewrites": user_rewrites
    }

    return Response(json.dumps(response_dict), status=200)

@app.route("/create_job", methods=["POST"])
def create_job():
    """
    Called when a new job is created. Creates Job object in DB.

    :param member_id: user's Memberstack ID
    :param job_name: job name
    """
    user = User.query.get(request.json["member_id"])
    job = Job(name=request.json["job_name"], word_count=0, user_id=user.id)
    db.session.add(job)
    db.session.commit()
    #return new job ID
    return Response(json.dumps({"job_id": job.id}), status=200)

@app.route("/remove_job", methods=["POST"])
def remove_job():
    """
    Removes shared job from database.

    :param member_id: member that job belonds to
    :param job_id: job to be removed
    """
    user = User.query.get(request.json["member_id"])
    job = Job.query.get(request.json["job_id"])
    
    for d in job.data:
        db.session.delete(d)
    
    db.session.delete(job)

    db.session.commit()
    return Response(status=200)

@app.route("/sync_job", methods=["POST"])
def sync_job():
    """
    Called when user has made changes to job data.

    :param member_id: user's Memberstack ID
    :param job_id: job that the changes have been made for
    :param job_name: job name
    :param data: list of dicts containing prompt, completion pairs
    """
    user = User.query.get(request.json["member_id"])
    if user is not None:
        try:
            job = Job.query.get(request.json["job_id"])
            #delete existing data belonging to job
            for data in [d for d in job.data if d.feedback=="user-upload"]:
                db.session.delete(data)
        except:
            #job has not been created
            job = Job(name=request.json["job_name"], word_count=0, user_id=user.id)
            db.session.add(job)
            db.session.flush()
    else:
        user = User(id = request.json["member_id"], name = request.json["name"], monthly_words = 0)
        job = Job(name=request.json["job_name"], word_count=0, user_id=user.id)
        db.session.add(job)
        db.session.add(user)
        db.session.flush()

    #add new data
    new_data = request.json["data"]

    word_count = 0
    for prompt_completion in new_data:
        prompt = prompt_completion["prompt"]
        completion = prompt_completion["completion"]
        db.session.add(Data(prompt=prompt, completion=completion, feedback="user-upload", job_id=job.id))
        word_count += len(completion.split())

    #run description if number of words is at least 300
    #if a new sample substantially changes the sum of samples
    new_samples = [d["completion"] for d in new_data]
    existing_samples = [d.completion for job in user.jobs for d in job.data]
    
    all_samples = new_samples + existing_samples
    all_samples_str = str("\n".join(sort_samples(all_samples)))[:8000]
    existing_samples_str = str("\n".join(sort_samples(existing_samples)))[:8000]

    #only consider first 8,000 characters ~ 2000 words
    if len(all_samples_str.split()) > 300 and all_samples_str!=existing_samples_str:
        try:
            messages = [{"role": "user", "content": f"Pretend the following text was written by you.\nText: {all_samples_str}\nGive an elaborate description of your writing style, language, audience, semantics, syntax. Speak in first person."}]
            description = turbo_openai_call(messages, 500, 0.4, 0.3)
        except:
            prompt = f"Pretend the following text was written by you.\nText: {all_samples_str}\nGive an elaborate description of your writing style, language, auidence, semantics, syntax. Speak in first person."
            description = openai_call(prompt, 500, 0.4, 0.3)
        #update user description
        user.description = description

        #pass decsription to Zapier
        url = "https://hooks.zapier.com/hooks/catch/14316057/bvhzkww/"
        response_dictionary = {
            "webflow_member_ID": user.id,
            "description": description
        }
        response = requests.post(url, data=json.dumps(response_dictionary))

    #update user record
    if job.name != request.json["job_name"]:
        job.name = request.json["job_name"]

    job.word_count = word_count

    db.session.commit()
    return Response(status=200)

@app.route("/sync_tasks", methods=["POST"])
def sync_tasks():
    user = User.query.get(request.json["member_id"])
    categories = list(set([str(d.category) for d in user.tasks])) #task, idea, rewrite

    for category in categories:
        tasks = [d for d in user.tasks if d.category==category]
        if len(tasks)>5:
            for task in tasks[5:]:
                if category=="task":
                    for source in task.sources:
                        db.session.delete(source)
                if task.feedback is None:
                    db.session.delete(task)
            db.session.commit()

    return Response(status=200)

@app.route("/handle_task", methods=["GET", "POST"])
def handle_task():
    """
    :param member_id: user's Memberstack ID
    :param job_id: job that the changes have been made for
    :param type: string, type of response to generate
    :param topic: string, subject of response
    :param additional: string, additional information user might provide
    :param search: bool, specifies whether to search the web
    """
    user = User.query.get(request.json["member_id"])
    job_id = int(request.json["job_id"])

    try:
        if job_id <= 0:
            #combine all job data
            samples = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback} for job in user.jobs for d in job.data]
        elif job_id > 0:
            job = Job.query.get(job_id)
            #get job data
            samples = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback} for d in job.data]
        else:
            samples = []
    except:
        #no job data
        samples = []
    
    category = request.json["type"]
    topic = request.json["topic"]
    additional = request.json["type"]
    search = request.json["search"]=="true"

    if search:
        search_result = search_web(topic)
    else:
        search_result = {"result": ""}

    maxlength = 2000-len(additional.split())-len(search_result["result"].split()) #prompt limit 3097 tokens (4097-1000 for completion)
    messages = construct_messages(user, samples, maxlength, topic)
    
    if search and search_result["result"] != "":
        context = search_result["result"]
        messages.append({"role": "system", "content": f"You may use following context to answer the next question.\nContext: {context}"})

    #add current prompt
    if len([d for d in messages if d["role"]=="user"]) > 0:
        messages.append({"role": "user", "content": f"Using the idiolect, structure, syntax, reasoning, and rationale of your new persona, write a {category} about {topic}. {additional} Do not mention this prompt in your response."})
        logit_bias = get_logit_bias([d["content"] for d in messages if d["role"]=="assistant"])
    else:
        #no user samples
        messages = [d for d in messages if d["role"]!="system"]
        messages.append({"role": "user", "content": f"Using a high degree of variation in your structure, syntax, and semantics, write a {category} about {topic}. {additional}"})
        logit_bias = {}

    completion = turbo_openai_call(messages, 1000, 1.2, 0.3, logit_bias)

    #store task data
    task = Task(prompt=f"Write a(n) {category} about {topic}.", completion=completion, category="task", user_id=user.id)
    db.session.add(task)
    
    if search and search_result["result"] != "":
        #if web search was successful, return sources
        sources = search_result["sources"]
        db.session.flush() #flush session to obtain task id
        for source in sources:
            db.session.add(Source(url=source["url"], display=source["display"], title=source["title"], preview=source["preview"], task_id=task.id))
    else:
        sources = []

    #update word count
    user.monthly_words += len(completion.split())
    db.session.commit()
    return Response(json.dumps({"completion": completion, "sources": sources}), status=200)

@app.route("/handle_rewrite", methods=["GET", "POST"])
def handle_rewrite():
    """
    :param member_id: user's Memberstack ID
    :param job_id: job that the changes have been made for
    :param text: string, text to be rewritten
    :param additional: string, additional information user might provide
    """
    user = User.query.get(request.json["member_id"])
    job_id = int(request.json["job_id"])

    try:
        if job_id == -1:
            #combine all job data
            samples = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback} for job in user.jobs for d in job.data]
        elif job_id > 0:
            job = Job.query.get(job_id)
            #get job data
            samples = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback} for d in job.data]
        else:
            samples = []
    except:
        #no job data
        samples = []

    text = request.json["text"]
    additional = request.json["additional"]
    
    maxlength = 2000-len(additional.split())
    messages = construct_messages(user, samples, maxlength, text)

    #add current prompt
    if len([d for d in messages if d["role"]=="user"]) > 0:
        messages.append({"role": "user", "content": f"Rewrite the following text using the same persona, structure, syntax, word choices, reasoning, and rationale used above. {additional} Text: {text}"})
        logit_bias = get_logit_bias([d["content"] for d in messages if d["role"]=="assistant"])
    else:
        messages.append({"role": "user", "content": f"Rewrite the following text using a high degree of variation in your structure, syntax, and semantics. {additional} Text: {text}"})
        logit_bias = {}

    completion = turbo_openai_call(messages, 1000, 1.2, 0.3, logit_bias)

    #store rewrite data    
    rewrite = Task(prompt = text[:120], completion = completion, category="rewrite", user_id=user.id)
    db.session.add(rewrite)
    #update word count
    user.monthly_words += len(completion.split())
    db.session.commit()

    return Response(json.dumps({"completion": completion}), status=200)

@app.route("/handle_idea", methods=["GET", "POST"])
def handle_idea():
    """
    :param member_id: user's Memberstack ID
    :param job_id: job that the changes have been made for
    :param text: string, text to be rewritten
    :param additional: string, additional information user might provide
    """
    user = User.query.get(request.json["member_id"])
    category = request.json["type"]
    topic = request.json["topic"]

    message = [{
        "role": "user", 
        "content": f"Generate ideas for my {category} about {topic}. Elaborate on each idea by providing specific examples of what content to include."
    }]

    completion = turbo_openai_call(message, 600, 0.3, 0.2)

    #store idea data
    idea = Task(prompt = f"Generate ideas for my {category} about {topic}.", completion = completion, category="idea", user_id=user.id)
    db.session.add(idea)
    #update word count
    user.monthly_words += len(completion.split())
    
    db.session.commit()

    return Response(json.dumps({"completion": completion}), status=200)

@app.route("/handle_feedback", methods=["GET", "POST"])
def handle_feedback():
    """
    Set task feedback and update user data.

    :param member_id: user's Memberstack ID
    :param job_id: job to be shared
    :param prompt: 
    :param completion:
    """
    job_id = int(request.json["job_id"])
    try:
        job = Job.query.get(job_id)
        prompt = request.json["prompt"]
        completion = request.json["completion"]
        feedback = request.json["feedback"]

        db.session.add(Data(prompt=prompt, completion=completion, feedback=feedback, job_id=job.id))
        db.session.commit()
    except:
        #if job number not specified, do nothing
        pass
    
    return Response(status=200)

@app.route("/share_job", methods=["POST"])
def share_job():
    """
    Creates dummy user and job for others to use.

    :param member_id: user's Memberstack ID
    :param job_id: job to be shared

    :param description: string, job description
    :param instructions: string, job instructions
    :param access: anyone, link, organisation
    """
    #create a dummy user to store job data
    user = User.query.get(request.json["member_id"])
    job = Job.query.get(int(request.json["job_id"]))

    description = request.json["description"]
    instructions = request.json["instructions"]
    access = request.json["access"]

    #create unique id
    u = uuid.uuid4()

    dummy_user = User(id = u.hex, name = user.name, monthly_words = 0, about = user.about, description = user.description)
    db.session.add(dummy_user)
    
    dummy_job = Job(name=job.name, word_count=0, user_id=dummy_user.id)
    db.session.add(dummy_job)

    db.session.flush()

    for d in job.data:
        db.session.add(Data(prompt=d.prompt, completion=d.completion, feedback="user-upload", job_id=dummy_job.id))

    #send data to Zapier
    url = "https://hooks.zapier.com/hooks/catch/14316057/3yq371j/"

    data = {
      "id": u.hex,
      "member": user.id,
      "user_description": user.description,
      "name": job.name,
      "description": description,
      "instructions": instructions,
      "access": access
    }

    response = requests.post(url, data=json.dumps(data))

    db.session.commit()
    return Response(status=200)

@app.route("/remove_shared_job", methods=["POST"])
def remove_shared_job():
    """
    Removes shared job from database.

    :param member_id: member that job belonds to
    :param job_id: job to be removed
    """
    counter = 0
    while counter<3:
        counter += 1
        url = "https://hooks.zapier.com/hooks/catch/14316057/3budn3o/"
        data = {
            "member": request.json["member_id"],
            "id": request.json["job_id"]
        }
        response = requests.post(url, data=json.dumps(data))

        if response.ok:
            #job id is user id for shared job
            dummy_user = User.query.get(request.json["job_id"])
            if dummy_user is not None:
                dummy_job = dummy_user.jobs[0]
                
                for d in dummy_job.data:
                    db.session.delete(d)
                
                db.session.delete(dummy_job)
                db.session.delete(dummy_user)

                db.session.commit()
            break
    return Response(status=200)


@app.route("/reset_monthly_words", methods=["GET"])
def reset_words():
    """
    Called at start of new month to reset user word counts.
    """
    users = User.query.all()
    for user in users:
        user.monthly_words = 0
    
    db.session.commit()
    return Response(status=200)

@app.route('/read_files', methods=['POST'])
def read_files():
    files = request.files.getlist('file')
    print([f.filename for f in files])
    texts = []
    for file in files:
        extension = file.filename.split(".")[-1]
        text = ""
        try:
            if extension == "docx":
                doc = Document(file)
                for para in doc.paragraphs:
                    text += "\n"
                    words = para.text.split()
                    for word in words:
                        if(len(text)+len(word)<8000):
                            text += f"{word} "
                        else:
                            break
            elif extension == "pdf":
                viewer = SimplePDFViewer(file)
                for canvas in viewer:
                    text = ''.join(canvas.strings)
                    for word in text.split():
                        if(len(text)+len(word)<8000):
                            text += f"{word} "
                        else:
                            break
            else:
                text = "Please upload either a .docx or .pdf"
            
            if text != "":
                texts.append(text.strip())
        except:
            return [f"Could not read file {file.filename}"]
    
    return Response(json.dumps({"texts": texts}), status=200)


if __name__ == "__main__":
    app.run(debug=True)
    