from flask import Flask, Response, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import URLType
from flask_cors import CORS

import psycopg2

import json
import uuid
from datetime import datetime

from virtuallyme import *

from docx import Document
from pdfreader import SimplePDFViewer

DATABASE_URL = "postgresql://virtuallyme_db_user:V3qyWKGBmuwpH0To2o5eVkqa1X4nqMhR@dpg-cfskiiarrk00vm1bp320-a.singapore-postgres.render.com/virtuallyme_db" #external

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
    monthly_words = db.Column(db.Integer, default=0)
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
    category = db.Column(db.String(100)) #task, question, idea, or rewrite
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now())
    score = db.Column(db.Integer)
    sources = db.relationship('Source', backref='sources', lazy='joined')
    feedback = db.Column(db.String(10)) #positive or negative
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'))
    job_id = db.Column(db.String(100), db.ForeignKey('job.id'))

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
            user_tasks.append({"prompt": task.prompt, "completion": task.completion, "feedback": task.feedback, "score": task.score, "created": str(task.created_at), "sources": sources})
        
        user_questions = []
        for question in [d for d in all_tasks if d.category=="question"]:
            sources = [{"url": d.url, "display": d.display, "title": d.title, "preview": d.preview} for d in question.sources]
            user_questions.append({"prompt": question.prompt, "completion": question.completion, "feedback": question.feedback, "score": question.score, "created": str(question.created_at), "sources": sources})

        user_ideas = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback, "score": d.score, "created": str(d.created_at)} for d in all_tasks if d.category=="idea"]
        user_rewrites = [{"prompt": d.prompt, "completion": d.completion, "feedback": d.feedback, "score": d.score, "created": str(d.created_at)} for d in all_tasks if d.category=="rewrite"]

        response_dict = {
            "description": user.description or "",
            "about": user.about or "",
            "words": user.monthly_words or 0,
            "user": user_jobs,
            "tasks": user_tasks[::-1],
            "questions": user_questions[::-1],
            "ideas": user_ideas[::-1],
            "rewrites": user_rewrites[::-1]
        }

        return Response(json.dumps(response_dict), status=200)
    except Exception as e:
        print(e)
        return Response(status=400)

@app.route("/get_data", methods=["GET"])
def get_data():
    """
    Called when user generates a task. Retrieves stored data.

    :param member_id: user's Memberstack ID
    :param job_id: job_id
    """
    try:
        user = User.query.get(request.headers.get("member_id"))
        job_id = int(request.headers.get("job_id"))

        description = user.description

        if job_id <= 0:
            #combine all job data
            samples = [{"completion": d.completion, "feedback": d.feedback} for job in user.jobs for d in job.data]
        elif job_id > 0:
            job = Job.query.get(job_id)
            #get job data
            samples = [{"completion": d.completion, "feedback": d.feedback} for d in job.data]
        else:
            samples = []
    except Exception as e:
        print(e)
        #no job data
        description = ""
        samples = []
    return Response(json.dumps({"samples": samples, "description": description}), status=200)

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
    try:
        user = User.query.get(request.json["member_id"])
        job = Job.query.get(request.json["job_id"])
        
        for d in job.data:
            db.session.delete(d)
        
        db.session.delete(job)

        db.session.commit()
        return Response(status=200)
    except Exception as e:
        print(e)
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

@app.route("/store_task", methods=["POST"])
def store_task():
    """
    :param member_id:
    :param category:
    :param prompt:
    :param completion:
    :param score:
    :param job_id:
    """
    user = User.query.get(request.json["member_id"])
    category = request.json["category"]
    prompt = request.json["prompt"]
    completion = request.json["completion"]
    score = request.json["score"]
    job = request.json["job_id"]

    task = Task(prompt=prompt, completion=completion, category=category, score=score, user_id=user.id, job_id=job)
    db.session.add(task)

    if category=="task" or category=="question":
        if "sources" in request.json:
            sources = request.json["sources"]
            db.session.flush() #flush session to obtain task id
            for source in sources:
                db.session.add(Source(url=source["url"], display=source["display"], title=source["title"], preview=source["preview"], task_id=task.id))

    
    #update user word count
    user.monthly_words += len(completion.split())
    db.session.commit()
    return Response(status=200)



@app.route("/handle_feedback", methods=["GET", "POST"])
def handle_feedback():
    """
    Set task feedback and update user data.

    :param member_id: user's Memberstack ID
    :param feedback: 'positive' or 'negative'
    :param completion: identify task by completion
    """
    ##job_id = int(request.json["job_id"])
    try:
        user = User.query.get(request.json["member_id"])
        completion = request.json["completion"]
        feedback = request.json["feedback"] #positive or negative

        #get all user tasks, ordered by created at column
        all_tasks = Task.query.filter_by(user_id=request.json["member_id"]).order_by(Task.created_at).all()
        for task in all_tasks:
            if task.completion == completion:
                #add feedback to task record
                task.feedback = feedback
                if feedback in ["positive", "negative"]:
                    job_id = task.job_id #job for which task was generated
                    
                    if job_id is not None and isinstance(job_id, int):
                        if job_id>0:
                            #create new data record in DB
                            prompt = task.prompt
                            db.session.add(Data(prompt=prompt, completion=completion, feedback=feedback, job_id=job_id))

                db.session.commit()
                break            

    except Exception as e:
        print(e) 
        return Response(status=500)



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
                text = "Unsupported filetype"
            
            if text != "":
                texts.append(text.strip())
        except Exception as e:
            print(e)
            return [f"Could not read file {file.filename}"]
    
    return Response(json.dumps({"texts": texts}), status=200)



if __name__ == "__main__":
    app.run(debug=True)