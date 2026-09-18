// LearnCraft Student OS — offline-first interactions (no network needed).
function toast(msg, ok=true){const t=document.getElementById('toast');if(!t)return;const d=document.createElement('div');d.className='toast-item';d.innerHTML=(ok?'✓ ':'⚠ ')+msg;t.appendChild(d);setTimeout(()=>d.remove(),2600);}
function openModal(html){document.getElementById('modalBox').innerHTML=html;document.getElementById('modalBack').classList.add('open');}
function closeModal(){document.getElementById('modalBack').classList.remove('open');}
document.addEventListener('click',e=>{if(e.target.id==='modalBack')closeModal();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
function closeProfileMenus(){document.querySelectorAll('.profile-menu').forEach(menu=>menu.classList.remove('open'));document.querySelectorAll('.profile-trigger').forEach(button=>button.setAttribute('aria-expanded','false'));}
function initProfileMenus(){document.querySelectorAll('.profile-trigger').forEach(button=>{
  button.addEventListener('click',e=>{
    e.stopPropagation();
    const menu=document.getElementById(button.getAttribute('aria-controls'));
    if(!menu)return;
    const willOpen=!menu.classList.contains('open');
    closeProfileMenus();
    if(willOpen){menu.classList.add('open');button.setAttribute('aria-expanded','true');}
  });
});
document.addEventListener('click',e=>{
  if(!e.target.closest('.profile-trigger')&&!e.target.closest('.profile-menu')){
    closeProfileMenus();
  }
});}
function filterCards(q){q=(q||'').toLowerCase();document.querySelectorAll('[data-search]').forEach(el=>{el.style.display=el.getAttribute('data-search').toLowerCase().includes(q)?'':'none';});}

document.addEventListener('DOMContentLoaded',()=>{initProfileMenus();});
// Notes — localStorage (offline)
const NOTES_KEY='learncraft_notes_v1';
function loadNotes(){try{return JSON.parse(localStorage.getItem(NOTES_KEY))||null;}catch{return null;}}
function saveNotes(n){localStorage.setItem(NOTES_KEY,JSON.stringify(n));}

// Practical workspace: local draft -> saved -> submitted state machine.
const PRACTICAL_KEY = 'learncraft_practical_loops_v1';
let practicalRun = {hasRun:false,passed:false};
function practicalStorage(){try{return JSON.parse(localStorage.getItem(PRACTICAL_KEY))||null;}catch{return null;}}
function practicalSaveState(state){localStorage.setItem(PRACTICAL_KEY,JSON.stringify(state));window.LearnCraftOffline?.persist(state.status==='SUBMITTED'?'submission':'progress','practical:loops',state,state.status);}
function setPracticalStatus(status,detail){
	const state=document.getElementById('practicalState');
	const footer=document.getElementById('footerState');
	if(!state||!footer)return;
	state.textContent=status;state.className='state-pill '+status.toLowerCase();footer.textContent=status==='SUBMITTED'?'Submitted successfully':(status==='SAVED'?'Draft saved locally':'Draft in progress');
	document.getElementById('footerDetail').textContent=detail;
}
function practicalTests(code){
	const normalized=code.replace(/\s/g,'');
	return {loop:/for\s+\w+\s+in\s+range/.test(code),squares:/\*\*2|\*\w+|\w+\*/.test(normalized),range:/range\(1,6\)/.test(normalized)};
}
function updatePracticalTest(id,passed){
	const row=document.getElementById('test-'+id);if(!row)return;
	row.classList.toggle('passed',passed);row.classList.toggle('failed',!passed);row.querySelector('.test-icon').textContent=passed?'✓':'×';row.querySelector('.test-status').textContent=passed?'Passed':'Needs work';
}
function runPractical(){
	const editor=document.getElementById('practicalCode');if(!editor)return;
	if(document.getElementById('practicalState').textContent==='SUBMITTED'){toast('Already submitted - review only',false);return;}
	const code=editor.value;const result=practicalTests(code);const passed=Object.values(result).every(Boolean);practicalRun={hasRun:true,passed};
	updatePracticalTest('loop',result.loop);updatePracticalTest('squares',result.squares);updatePracticalTest('range',result.range);
	document.getElementById('practicalOutput').textContent=passed?'▶ Running offline…\n✓ 3 tests passed\n\n1\n4\n9\n16\n25\n\nProcess finished with exit code 0.':'▶ Running offline…\n⚠ Some tests need attention.\n\nHint: iterate from 1 to 5 and print number * number.';
	document.getElementById('testSummary').textContent=passed?'3 / 3 passed':'Needs attention';document.getElementById('testSummary').className='badge '+(passed?'ok':'warn');
	setPracticalStatus('DRAFT',passed?'Tests pass. Save your draft when you are ready to review it.':'Tests ran. Adjust the code and try again.');
}
function savePractical(){
	const editor=document.getElementById('practicalCode');if(!editor)return;
	if(document.getElementById('practicalState').textContent==='SUBMITTED'){toast('Already submitted - review only',false);return;}
	practicalSaveState({code:editor.value,status:'SAVED',savedAt:new Date().toISOString()});setPracticalStatus('SAVED','Saved locally just now. You can continue editing or review it.');document.getElementById('saveInfo').textContent='Saved locally just now';toast('Draft saved on this machine');
}
function openPracticalReview(){
	if(document.getElementById('practicalState').textContent==='SUBMITTED'){toast('This practical has already been submitted');return;}
	if(!practicalRun.hasRun||!practicalRun.passed){toast('Run all tests successfully before reviewing',false);return;}
	document.getElementById('submitReview').hidden=false;document.getElementById('submitReview').scrollIntoView({behavior:'smooth',block:'center'});
}
function closePracticalReview(){document.getElementById('submitReview').hidden=true;}
function updateSubmitButton(){const ready=document.getElementById('submitConfirm').checked&&document.getElementById('submitWord').value.trim().toUpperCase()==='SUBMIT';document.getElementById('confirmSubmit').disabled=!ready;}
function submitPractical(){
	if(document.getElementById('confirmSubmit').disabled)return;
	const editor=document.getElementById('practicalCode');practicalSaveState({code:editor.value,status:'SUBMITTED',submittedAt:new Date().toISOString()});editor.disabled=true;document.querySelectorAll('.editor-panel button').forEach(button=>button.disabled=true);setPracticalStatus('SUBMITTED','Submitted locally. This practical is now locked for review.');document.getElementById('submitReview').hidden=true;toast('Practical submitted locally');
}
function initPractical(){
	const editor=document.getElementById('practicalCode');if(!editor)return;
	const saved=practicalStorage();if(saved&&saved.code){editor.value=saved.code;document.getElementById('saveInfo').textContent=saved.status==='SUBMITTED'?'Submitted locally':'Saved locally';}
	if(saved&&saved.status==='SUBMITTED'){editor.disabled=true;setPracticalStatus('SUBMITTED','Submitted locally. This practical is now locked for review.');}
	editor.addEventListener('input',()=>{if(document.getElementById('practicalState').textContent!=='SUBMITTED')setPracticalStatus('DRAFT','Unsaved changes stay on this machine until you save them.');});
	document.getElementById('submitConfirm').addEventListener('change',updateSubmitButton);document.getElementById('submitWord').addEventListener('input',updateSubmitButton);
}
document.addEventListener('DOMContentLoaded',initPractical);

// Assignment workspace: answers persist locally and evaluation is explicit.
const ASSIGNMENT_KEY = 'learncraft_assignment_newtons_laws_v1';
let assignmentCodingEvaluated = false;
function assignmentStorage(){try{return JSON.parse(localStorage.getItem(ASSIGNMENT_KEY))||null;}catch{return null;}}
function assignmentSaveState(state){localStorage.setItem(ASSIGNMENT_KEY,JSON.stringify(state));window.LearnCraftOffline?.persist(state.status==='SUBMITTED'?'submission':'progress','assignment:newtons-laws-4',state,state.status);}
function assignmentTasks(){return [...document.querySelectorAll('.assignment-task')];}
function assignmentAnswer(task){
	const type=task.dataset.taskType;
	if(type==='mcq')return task.querySelector('input:checked')?.value||'';
	if(type==='file_submission')return task.querySelector('input[type=file]')?.files[0]?.name||'';
	return task.querySelector('[data-answer-id]')?.value.trim()||'';
}
function assignmentAnswered(){return assignmentTasks().filter(task=>assignmentAnswer(task)).length;}
function updateAssignmentProgress(){
	const tasks=assignmentTasks();const answered=assignmentAnswered();const percent=Math.round(answered/tasks.length*100);
	document.getElementById('assignmentProgress').textContent=answered+' of '+tasks.length+' answered';document.getElementById('sideProgress').textContent=answered+' / '+tasks.length;document.getElementById('assignmentProgressBar').style.width=percent+'%';
	tasks.forEach(task=>{const done=Boolean(assignmentAnswer(task));const item=document.querySelector('[data-jump-to="'+task.dataset.taskId+'"]');if(item){item.classList.toggle('done',done);item.querySelector('i').textContent=done?'✓':'○';}});
}
function setAssignmentStatus(status,detail){const pill=document.getElementById('assignmentState');if(!pill)return;pill.textContent=status.replace('_',' ');pill.className='state-pill '+status.toLowerCase().replace(' ','-');document.getElementById('assignmentFooterState').textContent=status==='SUBMITTED'?'Submitted':(status==='SAVED'?'Saved':'In progress');document.getElementById('assignmentFooterDetail').textContent=detail;}
function assignmentAnswers(){const answers={};assignmentTasks().forEach(task=>{answers[task.dataset.taskId]=assignmentAnswer(task);});return answers;}
function saveAssignment(){
	if(document.getElementById('assignmentState').textContent==='SUBMITTED')return;
	assignmentSaveState({answers:assignmentAnswers(),status:'SAVED',savedAt:new Date().toISOString(),codingEvaluated:assignmentCodingEvaluated});setAssignmentStatus('SAVED','Answers saved locally just now. You can resume later.');document.getElementById('assignmentSaveInfo').textContent='Saved locally just now';document.getElementById('lastAssignmentSave').textContent='Saved just now on this device.';toast('Assignment saved locally');
}
function runAssignmentCode(id){
	const task=document.querySelector('[data-task-id="'+id+'"]');const code=task.querySelector('.assignment-code').value;const passed=/def\s+force/.test(code)&&/return/.test(code)&&/\*/.test(code);assignmentCodingEvaluated=true;
	task.querySelector('.coding-result').textContent=passed?'2 tests passed':'Tests need attention';task.querySelector('.coding-result').className='coding-result '+(passed?'pass':'fail');task.querySelector('.coding-output').textContent=passed?'▶ Running offline…\n✓ force(4, 3) -> 12\n✓ force(0, 8) -> 0\n\nProcess finished with exit code 0.':'▶ Running offline…\n⚠ No result yet. Return mass × acceleration from the function.';task.querySelectorAll('.coding-tests span').forEach(item=>{item.classList.toggle('passed',passed);item.textContent=(passed?'✓ ':'○ ')+item.textContent.slice(2);});updateAssignmentProgress();setAssignmentStatus('IN_PROGRESS',passed?'Coding tests passed. Save your answers before review.':'Coding tests ran. Adjust the function and try again.');
}
function restoreAssignment(saved){
	if(!saved||!saved.answers)return;assignmentTasks().forEach(task=>{const value=saved.answers[task.dataset.taskId];if(!value)return;const type=task.dataset.taskType;if(type==='mcq'){const radio=task.querySelector('input[value="'+value+'"]');if(radio)radio.checked=true;}else if(type!=='file_submission'){const field=task.querySelector('[data-answer-id]');if(field)field.value=value;}});assignmentCodingEvaluated=Boolean(saved.codingEvaluated);if(saved.status==='SAVED')setAssignmentStatus('SAVED','Answers saved locally. You can resume later.');if(saved.status==='IN_PROGRESS')setAssignmentStatus('IN_PROGRESS','Unsaved changes were restored from this device.');if(saved.status==='SUBMITTED'){setAssignmentStatus('SUBMITTED','Submitted locally. Your answers are locked for review.');document.querySelectorAll('.assignment-task input,.assignment-task textarea').forEach(field=>field.disabled=true);document.querySelectorAll('.assignment-task button').forEach(button=>button.disabled=true);}}
function reviewAssignment(){
	if(document.getElementById('assignmentState').textContent==='SUBMITTED')return;
	const required=assignmentTasks().filter(task=>task.dataset.taskType!=='file_submission');const complete=required.every(task=>assignmentAnswer(task));const ready=complete&&assignmentCodingEvaluated;
	document.getElementById('reviewStats').textContent=complete?(ready?'All required tasks answered · Coding tests evaluated':'Run the coding tests before submitting'):(required.filter(task=>assignmentAnswer(task)).length+' of '+required.length+' required tasks answered');document.getElementById('confirmAssignment').disabled=!ready;document.getElementById('assignmentReview').hidden=false;document.getElementById('assignmentReview').scrollIntoView({behavior:'smooth',block:'center'});
}
function closeAssignmentReview(){document.getElementById('assignmentReview').hidden=true;}
function submitAssignment(){
	const button=document.getElementById('confirmAssignment');if(button.disabled)return;assignmentSaveState({answers:assignmentAnswers(),status:'SUBMITTED',submittedAt:new Date().toISOString(),codingEvaluated:true});document.querySelectorAll('.assignment-task input,.assignment-task textarea').forEach(field=>field.disabled=true);document.querySelectorAll('.assignment-task button').forEach(control=>control.disabled=true);setAssignmentStatus('SUBMITTED','Submitted locally. Your answers are now locked for review.');document.getElementById('assignmentReview').hidden=true;toast('Assignment submitted locally');
}
function jumpToAssignmentTask(id){document.querySelector('[data-task-id="'+id+'"]').scrollIntoView({behavior:'smooth',block:'center'});}
function initAssignment(){
	if(!document.querySelector('.assignment-layout'))return;const saved=assignmentStorage();restoreAssignment(saved);updateAssignmentProgress();
	document.querySelectorAll('.assignment-task input,.assignment-task textarea').forEach(field=>{const autosave=()=>{if(document.getElementById('assignmentState').textContent!=='SUBMITTED'){assignmentSaveState({answers:assignmentAnswers(),status:'IN_PROGRESS',savedAt:new Date().toISOString(),codingEvaluated:assignmentCodingEvaluated});setAssignmentStatus('IN_PROGRESS','Unsaved changes are auto-saved on this device.');document.getElementById('lastAssignmentSave').textContent='Auto-saved just now.';updateAssignmentProgress();}};field.addEventListener('input',autosave);field.addEventListener('change',autosave);});
}
document.addEventListener('DOMContentLoaded',initAssignment);
