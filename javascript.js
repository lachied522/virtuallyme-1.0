import * as animations from "./animations.js"

function typeWriter(element, text){
    element.textContent = "";
    let index = 0;
    let interval = setInterval(() => {
        if (index < text.length){
            element.textContent += text.charAt(index);
            index++;
        } else {
            clearInterval(interval);
        }
    }, 10)
}

function waiting(element) {
    element.textContent = "Thinking";
    var ellipsis = ". "
    waitingInterval = setInterval(() => {
        element.textContent = "Thinking" + ellipsis;
        ellipsis += ". "
        if (ellipsis === ". . . . ") {
            ellipsis = ". ";
        }
    }, 400);
}

function updateUserWords(value){
    userWordCount = value;
    document.querySelectorAll("[customID='user-word-count']").forEach(element => {
        element.innerHTML = `Words this month: ${userWordCount}`;
    })
}

function newJob(jobName){
    let index = userJobs.length;
    let jobElement = document.querySelectorAll("[customID='job-container']")[index];
    //add job to job lists
    userJobs.push(jobName);
    //add job name to job Element
    jobElement.querySelector("[customID='job-name']").value = jobName;

    document.querySelectorAll("[customID='user-job-list']").forEach(element => {
        element.innerHTML += `<option>${jobName}</option>`
        element.value = jobName;
    });
    //increase job count
    document.querySelector("[customID='job-count']").innerHTML = String(userJobs.length)+"/"+String(maxJobs);
    //show job tab button
    var jobTabButtons = document.querySelectorAll(".job-tab");
    jobTabButtons[index].style.display = "block";
    jobTabButtons[index].innerHTML = jobName;
    //set text area resize to none prior to cloning
    jobElement.querySelector("[customID='sample-text']").style.resize = "none";

    return jobElement
}

function updateJobWords(jobElement, value){
    var wordCountElement = jobElement.querySelector("[customID='job-word-count']");
    wordCountElement.innerHTML = value.toLocaleString()+"/"+jobMaxWords.toLocaleString();
    let samplesGrid = jobElement.querySelector(".samples-grid");
    if (value===0){
        samplesGrid.querySelector("[customID='samples-empty-text']").style.display = "block";
    } else {
        samplesGrid.querySelector("[customID='samples-empty-text']").style.display = "none";
    }
}

function newSample(sampleWrapper, prompt, completion){
    let sampleClone = sampleWrapper.parentElement.cloneNode(true);
    sampleClone.querySelector("[customID='sample-prompt']").innerHTML = prompt;
    sampleClone.querySelector("[customID='sample-prompt-display']").innerHTML = prompt;
    sampleClone.querySelector("[customID='sample-text']").innerHTML = completion;
    //add remove button functionality
    sampleClone.querySelector("[customID='remove-button']").addEventListener("click", () => {
        removeSample(jobElement, sampleClone);
    });
    //cloneNode does not clone animations, must add back in
    sampleClone.querySelector(".sample-wrapper").addEventListener("click", () => {
        popupOpen(sampleClone.querySelector(".popup-wrapper"));
    });
    sampleClone.querySelector(".close-button-popup-module").addEventListener("click", () => {
        popupClose(sampleClone.querySelector(".popup-wrapper"));
    });
    sampleClone.querySelector(".btn-secondary.remove").addEventListener("click", () => {
        removeSampleConfirm(sampleClone);
    });
    sampleClone.querySelector(".btn-secondary.confirm").addEventListener("click", () => {
        popupClose(sampleClone.querySelector(".popup-wrapper"));
    });

    sampleClone.querySelector(".sample-wrapper").style.display = "flex";
    return sampleClone
}

function getUser(){
    const url = "http://virtuallyme.onrender.com/get_user";

    fetch(url, {
        method: "GET",
        headers: {
            'Content-Type': 'application/json',
            'member_id': member
        },
    })
    .then(response => response.json())
    .then(data => {
        //store task data
        var recentTasksContainer = document.querySelector("#recent-tasks");
        var taskModules = recentTasksContainer.querySelectorAll(".module");
        var taskHeaders = recentTasksContainer.querySelectorAll("[customID='tasks-header']");
        var taskBodies = recentTasksContainer.querySelectorAll("[customID='tasks-body']");
        for(let i = 0; i < data.tasks.length; i++){
            taskBodies[i].innerHTML = data.tasks[i].completion;
            taskHeaders[i].innerHTML = data.tasks[i].prompt;
            if(taskBodies[i].innerHTML !== ""){
                //show the module if non-empty
                taskModules[i].style.display = "block";
            }
        }
        if(taskBodies[0].innerHTML !== ""){
            document.querySelector("#tasks-empty-text").style.display = "none";
        }
        //store ideas data
        var recentIdeasContainer = document.querySelector("#recent-ideas");
        var ideaModules = recentIdeasContainer.querySelectorAll(".module");
        var ideaHeaders = recentIdeasContainer.querySelectorAll("[customID='ideas-header']");
        var ideaBodies = recentIdeasContainer.querySelectorAll("[customID='ideas-body']");
        for(let i=0; i < data.ideas.length; i++){
            ideaBodies[i].innerHTML = data.ideas[i].completion;
            ideaHeaders[i].innerHTML = data.ideas[i].prompt;
            if(ideaBodies[i].innerHTML !== ""){
                //show the module if non-empty
                ideaModules[i].style.display = "block";
            }
        }
        if(ideaBodies[0].innerHTML !== ""){
            document.querySelector("#ideas-empty-text").style.display = "none";
        }
        //update user word count
        updateUserWords(data.words);
        //add job data
        for(let i=0; i < data.user.length; i++){
            let newJobElement = newJob(data.user[i].name);
            //set job_id
            newJobElement.setAttribute("jobID", data.user[i].job_id);
            
            let samplesGrid = newJobElement.querySelector(".samples-grid");
            let sampleWrapper = samplesGrid.querySelector(".sample-wrapper");
            for(let j=0; j < data.user[i].data.length; j++){
                let newSample = newSample(sampleWrapper, data.user[i].data[j].prompt, data.user[i].data[j].completion);
                samplesGrid.appendChild(newSample);
            }
            updateJobWords(newJobElement, data.user.word_count);
        }
    })
    .catch(error => {
        console.log(error);
    })
}

function syncJob(jobElement) {
    const url = "http://virtuallyme.onrender.com/sync_job";

    var samplePrompts = jobElement.querySelectorAll("[customID='sample-prompt']");
    var sampleTexts = jobElement.querySelectorAll("[customID='sample-text']");

    var body = {
        "member_id": member, 
        "name": userName, 
        "job_name": jobElement.querySelector("[customID='job-name']").value, 
        "job_id": jobElement.getAttribute("jobID")
    };
    var dataArray = [];
    for(let i = 0; i < samplePrompts.length; i++){
        var prompt = samplePrompts[i].innerHTML;
        var text = sampleTexts[i].innerHTML;
        if(text !== ""){
            var data = {
                "prompt": prompt,
                "completion": text
            }
            dataArray.push(data);
        }
    }
    body["data"]=dataArray;
    fetch(url, {
        method: "POST",
        body: JSON.stringify(body),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then(response => response.json())
    .then(data => {
        console.log("Success:", data);
    })
    .catch(error => {
        console.error("Error loading data:", error);
    });
}

function createJob() {
    if(userJobs.length===maxJobs){
        //max jobs
        return
    } 
    const url = "http://virtuallyme.onrender.com/create_job"

    var form = document.querySelector("[customID='create-new-job']");
    newJobName = form.querySelector("[customInput='new-job-name']").value;

    var newJobElement = newJob(newJobName);
    //reset new job form
    form.reset();
    fetch(url, {
        method: "POST",
        body: JSON.stringify({"member_id": member, "job_name": newJobName}),
        headers: {
            "Content-Type": "application/json"
        },
    })
    .then(response => response.json())
    .then(data => {
        newJobElement.setAttribute("jobID", data.job_id);
        updateJobWords(newJobElement, 0);
    })
    .catch(error => {
        console.error("Error loading data:", error);
    });
}

function addSample(jobElement) {
    var form = jobElement.querySelector("[customID='add-sample']");
    var typeElement = form.querySelector("[customInput='type']");
    var topicElement = form.querySelector("[customInput='topic']");
    var textElement = form.querySelector("[customInput='text']");

    var wordCountElement = jobElement.querySelector("[customID='job-word-count']");
    var currentWords = parseInt(wordCountElement.innerHTML.split("/")[0]);
    var newWords = textElement.value.split(" ").length;

    if(currentWords+newWords>=jobMaxWords){
        console.log("max words");
        return
    }
    
    //check that no fields are empty
    var empty = [];
    if(typeElement.value.length===0){
        empty.push(typeElement);
    } else if(topicElement.value.length===0){
        empty.push(topicElement);
    } else if(textElement.value.length===0) {
        empty.push(textElement);
    } 
    if(empty.length===0){
        let samplesGrid = jobElement.querySelector(".samples-grid");
        let sampleWrapper = samplesGrid.querySelectorAll(".sample-wrapper")[0];
        let newSample = newSample(sampleWrapper, `Write a(n) ${typeElement.value} about ${topicElement.value}`, textElement.value);
        samplesGrid.appendChild(newSample);
        //reset elements (don't use form.reset())
        typeElement.value = "";
        topicElement.value = "";
        textElement.value = "";
        //increase job word count
        updateJobWords(jobElement, currentWords+newWords);
        //show save button
        jobElement.querySelector("[customID='save-button']").style.display = "flex";
        jobElement.querySelector("[customID='saved-button']").style.display = "none";
    } else {
        var originalColor = empty[0].style.borderColor;
        empty[0].style.borderColor = "#FFBEC2";
        setTimeout(function() {
            empty[0].style.borderColor = originalColor;
        }, 1500);
        return
    }
}

function removeSample(jobElement, sampleWrapper){
    let sampleWords = sampleWrapper.querySelector("[customID='sample-text']").value.split(" ").length;
    sampleWrapper.remove();
    //adjust word count
    let wordCountElement = jobElement.querySelector("[customID='job-word-count']");
    let currentWords = parseInt(wordCountElement.innerHTML.split("/")[0]);
    updateJobWords(jobElement, currentWords-sampleWords);
}

function configTask(taskWrapper){
    textareas = taskWrapper.querySelectorAll("textarea");
    textareas.forEach(textarea => {
        if(textarea.hasAttribute("customInput")){
            //maxlength for additional instructions 400 characters
            textarea.maxLength = 400;
        }
        textarea.addEventListener("input", () => {
            //set all textareas to scroll on input
            textarea.scrollTop = textarea.scrollHeight;
        })
    });
    //want job selector to update depending on value of "type" element
    var userJobsList = taskWrapper.querySelector("[customID='user-job-list']");
    var typeElement = taskWrapper.querySelector("[customInput='type']");
    typeElement.addEventListener("change", ()=>{
        for(let i=0; i<userJobs.length; i++){
            if(userJobs[i].toLowerCase().includes(typeElement.value.toLowerCase())){
                userJobsList.value = userJobs[i];
                return
            }
        }
    });
}

function share(jobElement){
    //call sync function first
    syncJob(jobNumber);
    const url = "http://virtuallyme.onrender.com/share_job";

    var form = jobElement.querySelector("[customID='share-job']");

    var body = {
        "member_id": member,
        "job_id": jobElement.getAttribute("jobID"),
        "description": form.querySelector("[customInput='description']").value,
        "instructions": form.querySelector("[customInput='instructions']").value,
        "access": form.querySelector("[customInput='access']").value
    };

    fetch(url, {
        method: "POST",
        body: JSON.stringify(body),
        headers: {
            "Content-Type": "application/json"
        },
    })
}

/////####################////////////
function removeSharedJob(id){
    const url = "https://eotb00w2hzgv89k.m.pipedream.net";

    var body = {
        "id": id
    };

    fetch(url, {
        method: "POST",
        body: JSON.stringify(body),
        headers: {
            "Content-Type": "application/json"
        },
    })
}

function submitTask() {
    if(isWaiting){
        //if still waiting, do nothing
        return
    } else if(userWordCount > userMonthlyWords){
        document.querySelector("[customID='task-output']").textContent = "You have reached your maximum word limit for this month.\n\nUpgrade your plan to increase your limit."
        return
    }
    const url = "http://virtuallyme.onrender.com/handle_task";
    var form = document.querySelector("[customID='submit-task']");
    var typeElement = form.querySelector("[customInput='type']");
    var topicElement = form.querySelector("[customInput='topic']");
    var searchElement = form.querySelector("[customID='search-toggle']");

    //get ID of selected job
    var jobIndex = form.querySelector("[customID='user-job-list']").selectedIndex-1;
    if(jobIndex<0||jobIndex>userJobs.length){
        var jobID = -1
    } else {
        var jobID = document.querySelectorAll("[customID='job-container']")[jobIndex].getAttribute("jobID");
    }
    //check if either typeElement or topic are missing
    var empty = [];
    if(typeElement.value===""){
        empty.push(typeElement);
    }
    if(topicElement.value===""){
        empty.push(topicElement);
    }
    var additionalElement = form.querySelector("[customInput='additional']");
    const data = {
        "name": userName, 
        "member_id": member,
        "job_id": jobID, 
        "type": typeElement.value, 
        "topic": topicElement.value, 
        "additional": additionalElement.value,
        "search": searchElement.getAttribute("on")
    };

    //if neither type or topic element is missing
    if(empty.length==0){
        var destination = document.querySelector("[customID='task-output']");
        waiting(destination);
        isWaiting = true;
        //reset feedback bar
        var feedbackBar = document.querySelector(".feedback-bar");
        feedbackBar.style.display = "flex";
        var feedbackText = document.querySelector(".feedback-text");
        feedbackText.style.display = "none";
        fetch(url, {
            method: "POST",
            body: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json'
            },
        })
        .then(response => response.json())
        .then(data => {
            isWaiting = false;
            clearInterval(waitingInterval);
            typeWriter(destination, data.completion);
            var words = data.completion.split(" ").length;
            //update task word count
            document.querySelector("[customID='task-word-count']").innerHTML = `Word count: ${words}`;
            //update user word count
            updateUserWords(userWordCount+words);
            //update tasks list
            var recentTasksContainer = document.querySelector("#recent-tasks");
            var modules = recentTasksContainer.querySelectorAll(".module");
            var taskHeaders = recentTasksContainer.querySelectorAll("[customID='tasks-header']");
            var taskBodies = recentTasksContainer.querySelectorAll("[customID='tasks-body']");
            //if no existing tasks
            if(taskBodies[0].innerHTML === ""){
                document.querySelector("#tasks-empty-text").style.display = "none";
                modules[0].style.display = "block";
            } else {
                //move tasks list
                for(let i=taskBodies.length-1; i > 0; i--){
                    taskBodies[i].innerHTML = taskBodies[i-1].innerHTML;
                    taskHeaders[i].innerHTML = taskHeaders[i-1].innerHTML;
                    if(taskBodies[i].innerHTML !== ""){
                        //show the module if non-empty
                        modules[i].style.display = "block";
                    }
                }
            }
            //set first task to the one just completed
            taskHeaders[0].innerHTML = `Write a(n) ${typeElement.value} about ${topicElement.value}`;
            taskBodies[0].innerHTML = data.completion;
        })
        .catch(error => {
            isWaiting = false;
            clearInterval(waitingInterval);
            destination.textContent = "There was an error, please try again later. I apologise for the inconvenience.";
            console.log(error);
        })
    } else {
        var originalColor = empty[0].style.borderColor;
        empty[0].style.borderColor = "#FFBEC2";
        setTimeout(function() {
            empty[0].style.borderColor = originalColor;
        }, 1500);
        return
    }             
}

function generateIdeas() {
    if(isWaitingIdea){
        //if still waiting, do nothing
        return
    } else if(userWordCount>userMonthlyWords){
        document.querySelector("[customID='ideas-output']").textContent = "You have reached your maximum word limit for this month.\n\nUpgrade your plan to increase your limit."
        return
    }
    const url = "http://virtuallyme.onrender.com/handle_idea";
    var form = document.querySelector("[customID='ideas-form']");
    var typeElement = form.querySelector("[customInput='type']");
    var topicElement = form.querySelector("[customInput='topic']");

    //check if either typeElement or topic are missing
    var empty = [];
    if(typeElement.value===""){
        empty.push(typeElement);
    }
    if(topicElement.value===""){
        empty.push(topicElement);
    }
    const data = {
        "name": userName, 
        "member_id": member, 
        "type": typeElement.value, 
        "topic": topicElement.value
    };
    if(empty.length==0){
        var destination = document.querySelector("[customID='ideas-output']");
        waiting(destination);
        isWaitingIdea = true;
        fetch(url, {
            method: "POST",
            body: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json'
            },
        })
        .then(response => response.json())
        .then(data => {
            isWaitingIdea = false;
            clearInterval(waitingInterval);
            typeWriter(destination, data.completion);
            var words = data.completion.split(" ").length;
            //update task word count
            document.querySelector("[customID='idea-word-count']").innerHTML = `Word count: ${words}`;
            //update user word count
            updateUserWords(userWordCount+words);
            //update tasks list
            var recentIdeasContainer = document.querySelector("#recent-ideas");
            var modules = recentIdeasContainer.querySelectorAll(".module");
            var ideaHeaders = recentIdeasContainer.querySelectorAll("[customID='ideas-header']");
            var ideaBodies = recentIdeasContainer.querySelectorAll("[customID='ideas-body']");
            //if no existing tasks
            if(ideaBodies[0].innerHTML === ""){
                document.querySelector("#ideas-empty-text").style.display = "none";
                modules[0].style.display = "block";
            } else {
                //move tasks list
                for(let i=ideaBodies.length-1; i > 0; i--){
                    ideaBodies[i].innerHTML = ideaBodies[i-1].innerHTML;
                    ideaHeaders[i].innerHTML = ideaHeaders[i-1].innerHTML;
                    if(ideaBodies[i].innerHTML !== ""){
                        //show the module if non-empty
                        modules[i].style.display = "block";
                    }
                }
            }
            //set first task to the one just completed
            ideaHeaders[0].innerHTML = `Generate content ideas for my ${data.completion}`;
            ideaBodies[0].innerHTML = data.completion;
            
        })
        .catch(error => {
            isWaitingIdea = false;
            clearInterval(waitingInterval);
            destination.textContent = "There was an error, please try again later. I apologise for the inconvenience.";
            console.log(error);
        })
    } else {
        var originalColor = empty[0].style.borderColor;
        empty[0].style.borderColor = "#FFBEC2";
        setTimeout(function() {
            empty[0].style.borderColor = originalColor;
        }, 1500);
        return
    }
}

function submitRewrite() {
    if(isWaitingRewrite){
        //if still waiting, do nothing
        return
    } else if(userWordCount > userMonthlyWords){
        document.querySelector("[customID='rewrite-output']").textContent = "You have reached your maximum word limit for this month.\n\nUpgrade your plan to increase your limit."
        return
    }
    const url = "http://virtuallyme.onrender.com/handle_rewrite";
    var form = document.querySelector("[customID='submit-rewrite']");
    var textElement = form.querySelector("[customInput='text']");
    //get ID of selected job
    var jobIndex = form.querySelector("[customID='user-job-list']").selectedIndex-1;
    if(jobIndex<0||jobIndex>userJobs.length){
        var jobID = -1
    } else {
        var jobID = document.querySelectorAll("[customID='job-container']")[jobIndex].getAttribute("jobID");
    }
    var additionalElement = form.querySelector("[customInput='additional']");
    const data = {
        "name": userName, 
        "member_id": member,
        "job_id": jobID,
        "text": textElement.value, 
        "additional": additionalElement.value
    };

    //check text element is not empty
    if(textElement.value !== ""){
        var destination = document.querySelector("[customID='rewrite-output']");
        waiting(destination);
        isWaitingRewrite = true;
        fetch(url, {
            method: "POST",
            body: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json'
            },
        })
        .then(response => response.json())
        .then(data => {
            isWaitingRewrite = false;
            clearInterval(waitingInterval);
            typeWriter(destination, data.completion);
            var words = data.completion.split(" ").length;
            //update task word count
            document.querySelector("[customID='rewrite-word-count']").innerHTML = `Word count: ${words}`;
            //update user word count
            updateUserWords(userWordCount+words);
        })
        .catch(error => {
            isWaitingRewrite = false;
            clearInterval(waitingInterval);
            destination.textContent = "There was an error, please try again later. I apologise for the inconvenience.";
            console.log(error);
        })
    } else {
        var originalColor = textElement.style.borderColor;
        textElement.style.borderColor = "#FFBEC2";
        setTimeout(function() {
            textElement.style.borderColor = originalColor;
        }, 1500);
        return
    }      
}

function searchToggle(searchElement){
    if(searchElement.getAttribute("on")==="true"){
        searchElement.setAttribute("on", "false");
    } else {
        searchElement.setAttribute("on", "true");
    }
}

function sendFeedback(feedback){
    const url = "http://virtuallyme.onrender.com/handle_feedback";
    //get recent task
    var recentTasksContainer = document.querySelector("[customID='recent-tasks']");
    var prompt = recentTasksContainer.querySelectorAll("[customID='tasks-header']")[0].innerHTML;
    var completion = recentTasksContainer.querySelectorAll("[customID='tasks-body']")[0].innerHTML;

    var data = {"member": member, "feedback": feedback, "prompt": prompt, "completion": completion}
    fetch(url, {
        method: "POST",
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json'
        },
    });

    //show feedback text
    document.querySelector(".feedback-bar").style.display = "none";
    document.querySelector(".feedback-text").style.display = "block";
}

function pageLoad(){
    getUser();
    if(userJobs.length>0){
        //hide welcome popup
        document.querySelector(".welcome-popup").style.display = "none"; 
    }
    hidePreloader();
    //add create job funcionality
    document.querySelector("[customID='create-job-button']").addEventListener("click", ()=> {
        createJob();
    });
    //add functionality to jobs 
    document.querySelectorAll("[customID='job-container']").forEach(jobElement => {    
        jobElement.querySelector("[customID='add-button']").addEventListener("click", () => {
            addSample(jobElement);
        });

        jobElement.querySelector("[customID='save-button']").addEventListener("click", () => {
            syncJob(jobElement);
        });

        jobElement.querySelector("[customID='share-button']").addEventListener("click", () => {
            share(jobElement);
        });
    });
    //add functionality to task wrappers
    document.querySelectorAll("[customID='submit-task']").forEach(taskElement => {
        configTask(taskElement);
    });
    //add search toggle functionality
    document.querySelectorAll("[customID='search-toggle']").forEach(searchElement => {
        searchElement.addEventListener("click", () => {
            searchToggle(searchElement);
        });
        searchElement.setAttribute("on", "false");
    });
    //add feedback button functionality
    document.querySelector("[customID='positive-feedback-button']").addEventListener("click", function() {
        sendFeedback('positive');
    });
    document.querySelector("[customID='negative-feedback-button']").addEventListener("click", function() {
        sendFeedback('negative');
    });
}

let isWaiting = false;
let isWaitingRewrite = false;
let isWaitingIdea = false;

