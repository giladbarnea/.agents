const S = {};
const appear = (p, at, content) => rise(ease((p-at)/.12),content);
const label = (x,y,text,size=28,fill=C.ink) => T(x,y,text,{size,fill,font:'mono'});
const heading = (text,fill=C.ink) => T(80,94,text,{size:24,fill,font:'mono',anchor:'start'});
const title = (text,y=180,size=59,fill=C.ink) => T(540,y,text,{size,fill,weight:700});
const arrow = (path,p,at=.1,color=C.ink) => line(path,ease((p-at)/.15),{stroke:color,width:7,marker:color===C.green?'arrowGreen':color===C.red?'arrowRed':color===C.paper?'arrowPaper':'arrowInk'});
const chip = (x,y,w,text,fill=C.paper,size=27,color=C.ink) => `<rect x="${x}" y="${y}" width="${w}" height="64" rx="14" fill="${fill}" stroke="${C.ink}" stroke-width="3"/>`+label(x+w/2,y+43,text,size,color);
const open = (number,text,fill=C.mustard) => panel(fill)+heading(`OPEN ${number} / 4`)+title(text);
const today = text => `<rect x="60" y="773" width="960" height="65" rx="12" fill="${C.paper}" stroke="${C.ink}" stroke-width="2"/>`+label(540,814,'TODAY · '+text,Math.min(24,900/((text.length+8)*.62)),C.navy);
const tinyQuestion = (x,y,name='Q') => bubble(x,y,110,85,[name],{size:36});
const clock = (x,y,r=55) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${C.paper}" stroke="${C.ink}" stroke-width="4"/>`+line(`M${x} ${y-r*.65} L${x} ${y} L${x+r*.5} ${y}`,1,{width:6});
const allowance = (x,y,spent) => [0,1,2].map(i=>`<circle cx="${x+i*65}" cy="${y}" r="22" fill="${i<spent?C.red:C.paper}" stroke="${C.ink}" stroke-width="3"/>`+(i<spent?cross(x+i*65,y,22,C.paper):'')).join('');
const closed = (x,y,w=210) => `<rect x="${x}" y="${y}" width="${w}" height="125" rx="10" fill="${C.sky}" stroke="${C.ink}" stroke-width="4"/>`+line(`M${x-10} ${y+20} L${x+w+10} ${y+20}`,1,{width:7})+label(x+w/2,y+85,'CLOSED',31,C.navy);

S.r01 = p => panel(C.cream)
 + title('One job, two teams',175,85)
 + appear(p,.05,chip(100,260,395,'Pi: coding assistant',C.sky,29))
 + appear(p,.18,tag(620,292,'update',{size:40}))
 + appear(p,.26,[200,450,700,920].map((x,i)=>card(x-75,465,150,210,['extension A','extension B','extension C','extension D'][i])).join(''))
 + [200,450,700,920].map((x,i)=>check(x,635,70,C.green,ease((p-.42-i*.06)/.1))).join('')
 + appear(p,.70,label(540,800,'add-ons maintained · less to remember',29,C.navy));

S.r02 = p => panel(C.cream)+heading('MAIN AGENTS AND THEIR DELEGATES')
 + tree(285,280,535,[130,285,440],'fix',p*3.2,{rootR:65,childR:37})
 + tree(795,280,535,[640,795,950],'rev',p*3.2,{rootR:65,childR:37,start:.3})
 + appear(p,.05,label(285,160,'main fixer',35,C.red)+label(795,160,'main reviewer',35,C.navy))
 + appear(p,.28,label(285,650,'fixer delegates',29,C.red)+label(795,650,'reviewer delegates',29,C.navy))
 + appear(p,.5,label(540,745,'delegates = specialists',31))
 + appear(p,.65,label(285,812,'Opus 5.5',25,C.red)+label(795,812,'Astra',25,C.navy));

S.r03 = p => panel(C.sky)+heading('WHO EDITS, WHO CHECKS')
 + appear(p,.0,agent(170,330,70,'fix')+label(170,455,'edits',31,C.red))
 + arrow('M250 330 L365 330',p,.13)
 + appear(p,.20,box3d(400,465,220,240,{label:'extension copy'}))
 + arrow('M655 330 L800 330',p,.38)
 + appear(p,.46,agent(900,330,70,'rev')+label(900,455,'checks',31,C.navy))
 + appear(p,.61,chip(160,660,760,'main agents assign work; never edit code',C.paper,27))
 + appear(p,.73,label(540,795,'reports travel through the system',26));

S.r04 = p => panel(C.cream)+heading('AN ITEM IS A PATCH OR A QUESTION')
 + appear(p,.0,doc(140,230,220,260,{title:'patch',diff:true})+label(250,555,'code changes',30,C.red))
 + appear(p,.12,bubble(650,270,270,145,['question for you'],{size:29})+label(785,555,'choice for you',29,C.navy))
 + appear(p,.23,agent(540,360,65,'rev'))
 + stamp(270,660,'approve',C.green,ease((p-.4)/.12),{w:230,size:35})
 + stamp(790,660,'revise',C.red,ease((p-.53)/.12),{w:230,size:35})
 + appear(p,.7,label(540,805,'main reviewer passes decisions unchanged',25));

S.r05 = p => panel(C.pink)+heading('THE MAIN FIXER IS THE LAST GATE')
 + appear(p,.0,agent(230,440,88,'fix',{main:true})+label(230,585,'main fixer',29))
 + arrow('M340 420 Q450 245 650 245',p,.12,C.green)
 + appear(p,.22,chip(680,205,280,'release',C.lightGreen,34)+label(820,330,'send forward',25))
 + arrow('M340 450 L650 450',p,.3,C.red)
 + appear(p,.4,agent(720,450,42,'fix')+label(870,445,'return',33,C.red)+label(870,495,'send back',23))
 + arrow('M340 480 Q450 660 650 660',p,.49)
 + appear(p,.60,clock(715,660,40)+label(875,653,'hold',35)+label(875,707,'wait for answer',22));

S.r06 = p => panel(C.night)+heading('RELEASE: ONLY APPROVED WORK',C.paper)
 + appear(p,.0,doc(95,230,205,255,{title:'reviewed files',diff:true}))
 + stamp(200,545,'approved',C.green,ease((p-.12)/.12),{w:240,size:31})
 + arrow('M320 350 L490 350',p,.22,C.paper)
 + appear(p,.31,phone(540,170,330,550)+chip(580,350,250,'Push',C.green,42,C.paper))
 + appear(p,.45,label(705,490,'tap to publish',27,C.navy)+label(705,550,'GitHub: shared code',22,C.navy))
 + appear(p,.6,label(230,675,'same files',26,C.paper)+label(230,722,'same starting version',21,C.paper))
 + appear(p,.74,label(540,800,'product change = changes what users see',25,C.mustard));

S.r07 = p => panel(C.cream)+heading('RETURN = SEND BACK FOR REVISION')
 + appear(p,.0,doc(420,165,240,250,{title:'review findings'}))
 + appear(p,.1,chip(100,240,280,'original text',C.sky,27)+chip(710,240,280,'fixer’s reasons',C.pink,27))
 + arrow('M420 420 Q290 460 240 565',p,.24,C.red)
 + appear(p,.34,agent(220,640,65,'fix')+label(220,755,'revise work',28,C.red))
 + arrow('M300 640 L750 640',p,.46)
 + appear(p,.57,agent(850,640,65,'rev')+label(850,755,'review again',28,C.navy))
 + appear(p,.70,label(540,545,'the same reasons',27));

S.r08 = p => panel(C.pink)+heading('THREE RETURNS, THEN HANDOFF NOTES')
 + appear(p,.0,allowance(475,225,3)+label(540,310,'three returns used',29))
 + appear(p,.17,agent(270,450,62,'fix')+agent(810,450,62,'rev'))
 + arrow('M270 520 L270 585',p,.28)+arrow('M810 520 L810 585',p,.36)
 + appear(p,.42,doc(190,600,160,150,{title:'handoff notes'})+doc(730,600,160,150,{title:'handoff notes'}))
 + appear(p,.59,chip(420,440,240,'hold: +0',C.mustard,28))
 + appear(p,.73,label(540,815,'next specialists read both notes',26));

S.r09 = p => panel(C.cream)+heading('HOLD = WAIT FOR ONE NAMED ANSWER')
 + appear(p,.0,card(120,520,220,220,'extension A')+card(740,520,220,220,'extension B'))
 + line('M340 625 L740 625',ease((p-.08)/.15),{width:9})
 + appear(p,.15,`<circle cx="540" cy="625" r="58" fill="${C.mustard}" stroke="${C.ink}" stroke-width="4"/>`+label(540,643,'X',48))
 + appear(p,.24,agent(270,260,75,'fix',{main:true})+bubble(420,190,525,150,['Use design X for both?'],{size:32}))
 + stamp(230,680,'HOLD',C.navy,ease((p-.44)/.12),{w:220,size:37})
 + stamp(850,680,'HOLD',C.navy,ease((p-.53)/.12),{w:220,size:37})
 + appear(p,.69,label(665,430,'main fixer asks directly',27,C.red));

S.r10 = p => panel(C.sky)+heading('ONE QUESTION AT A TIME')
 + phone(120,170,350,600)
 + appear(p,.05,bubble(155,320,280,145,['Use design X?'],{size:30}))
 + appear(p,.2,chip(155,510,280,'Yes for A',C.lightGreen,28))
 + appear(p,.15,chip(650,250,280,'next question',C.paper,27)+chip(680,350,280,'then another',C.paper,27))
 + arrow('M480 540 Q590 640 685 640',p,.35)
 + appear(p,.46,agent(790,640,66,'fix',{main:true}))
 + appear(p,.68,label(790,800,'handle answer first',25));

S.r11 = p => panel(C.cream)+heading('LATE OR PARTIAL ANSWERS')
 + appear(p,.0,bubble(100,200,360,145,['Yes for A.', 'Unsure about B.'],{size:31,fill:C.lightGreen}))
 + appear(p,.13,agent(740,260,75,'fix',{main:true})+label(740,385,'current main fixer',27))
 + arrow('M480 270 L640 270',p,.22)
 + appear(p,.33,agent(200,590,62,'fix',{ghost:true})+label(200,710,'retired = replaced',24,C.grey))
 + appear(p,.42,doc(410,520,150,170,{title:'private notes'}))
 + arrow('M590 605 L735 605',p,.53)
 + appear(p,.64,agent(840,605,68,'fix',{fresh:true})+label(840,735,'new delegate',28));

S.r12 = p => panel(C.mustard)+heading('A RUN = ONE BATCH OF MAINTENANCE')
 + appear(p,.0,label(285,230,'new work + idle',29)+label(795,230,'usage limit reached',27))
 + appear(p,.14,agent(205,420,60,'fix',{main:true,fresh:true})+agent(365,420,60,'rev',{main:true,fresh:true}))
 + appear(p,.3,agent(715,420,60,'fix',{main:true})+agent(875,420,60,'rev',{main:true}))
 + appear(p,.45,chip(100,590,370,'fresh agents',C.paper,30)+chip(610,590,370,'same agents wait',C.paper,28))
 + appear(p,.68,label(540,785,'three scheduled checks each day',28));

S.r13 = p => panel(C.sky)+heading('NEW PROGRAM, SAME SAVED CONVERSATION')
 + appear(p,.0,chip(80,225,380,'first piece of work',C.paper,26)+chip(620,225,380,'next piece of work',C.paper,26))
 + appear(p,.12,agent(270,400,65,'fix',{main:true})+agent(810,400,65,'fix',{main:true}))
 + arrow('M270 490 Q270 620 365 650',p,.25)
 + appear(p,.36,box3d(395,745,275,165,{label:'saved conversation'}))
 + arrow('M700 650 Q810 650 810 490',p,.52)
 + appear(p,.69,label(540,155,'wait for messages → finish → close',27,C.navy));

S.r14 = p => panel(C.mustard)+heading('FIRST TRIAL: NOTICE WHAT IS NO LONGER NEEDED')
 + appear(p,.0,tag(100,205,'Pi 1.4.0',{fill:C.paper,size:45}))
 + appear(p,.1,label(610,325,'Pi already fixes the problem',29))
 + appear(p,.2,doc(150,420,270,280,{title:'pi-how-much-ctx-have',diff:true})+doc(660,420,270,280,{title:'tool-output-kit',diff:true}))
 + cross(285,565,160,C.red,ease((p-.43)/.14))
 + cross(795,565,160,C.red,ease((p-.57)/.14))
 + appear(p,.73,label(540,810,'discard both · no question needed',27));

S.r15 = p => panel(C.cream)+heading('THE TEAM EXTENSION HAS AN OLDER PROMISE')
 + appear(p,.0,doc(425,190,230,245,{title:'pi-simple-team',diff:true}))
 + arrow('M425 350 Q270 400 230 500',p,.16)+arrow('M655 350 Q810 400 850 500',p,.28)
 + appear(p,.27,tag(110,585,'Pi 1.3',{size:36})+label(250,690,'extra fix still needed',24,C.red))
 + appear(p,.4,tag(700,585,'Pi 1.4',{size:36,fill:C.lightGreen})+label(845,690,'already fixed by Pi',24,C.green))
 + appear(p,.63,chip(235,765,610,'ask before removing the extra code',C.paper,27));

S.r16 = p => panel(C.navy)+heading('CURRENT STATUS',C.paper)
 + title('Built and tested',205,75,C.paper)
 + appear(p,.08,box3d(130,535,230,220,{face:C.lightGreen,label:''})+check(250,440,110,C.paper))
 + appear(p,.24,label(250,630,'tests passed',31,C.paper))
 + arrow('M400 420 L555 420',p,.34,C.paper)
 + appear(p,.44,`<rect x="625" y="320" width="280" height="140" rx="70" fill="${C.ink}" stroke="${C.paper}" stroke-width="4"/><circle cx="695" cy="390" r="55" fill="${C.red}"/>`+label(770,545,'LIVE: OFF',43,C.paper))
 + appear(p,.62,label(540,725,'later: restart automatically after a crash',24,C.paper))
 + appear(p,.76,label(540,805,'later: choose a default if you do not reply',23,C.paper));

S.r17 = p => panel(C.cream)+heading('BEND: A TOOL FOR CHECKING DESIGN RULES')
 + appear(p,.0,doc(100,220,255,285,{title:'rules = laws'})+label(225,565,'no rejected work',25,C.navy)+label(225,605,'may publish',25,C.navy))
 + arrow('M375 365 L475 365',p,.18)
 + appear(p,.26,`<rect x="510" y="225" width="440" height="330" rx="20" fill="${C.sky}" stroke="${C.ink}" stroke-width="4"/>`+label(730,290,'Bend',46,C.navy)+agent(640,405,38,'fix')+agent(820,405,38,'rev')+line('M682 405 L778 405',1,{width:6})+label(730,505,'simplified system',25))
 + appear(p,.53,stamp(730,650,'CHECKS PASS',C.green,1,{w:330,size:32,rotate:0}))
 + appear(p,.70,label(540,805,'a model, not the running program',29));

S.r18 = p => panel(C.cream)+heading('OPEN: APPROVE THE RULES AND THEIR CONNECTION')
 + appear(p,.0,`<rect x="95" y="240" width="340" height="300" rx="20" fill="${C.sky}" stroke="${C.ink}" stroke-width="4"/>`+label(265,310,'Bend model',33,C.navy)+T(265,440,'52',{size:115,fill:C.navy,weight:700})+check(370,490,65,C.green))
 + appear(p,.2,box3d(735,510,190,230,{label:'working code'}))
 + line('M460 385 L695 385',ease((p-.3)/.15),{width:7,dash:'15 13'})
 + appear(p,.41,T(580,365,'?',{size:90,fill:C.red,weight:700}))
 + appear(p,.55,label(540,665,'approve rule meanings; check the code',29))
 + appear(p,.69,label(540,720,'no guarantee that every task can finish',26,C.red))
 + today('model separate; connection not approved');

function countChoice(p,followup) {
  const spentLeft=followup?2:1, spentRight=followup?3:2;
  return open(1,'One return, or two?')
   + label(285,250,'count the pair once',27)+chip(650,207,340,'BUILD: count each',C.navy,25,C.paper)
   + appear(p,.03,doc(155,300,110,135,{title:'patch',diff:true})+tinyQuestion(300,320)+doc(655,300,110,135,{title:'patch',diff:true})+tinyQuestion(800,320))
   + arrow('M210 445 Q230 485 280 515',p,.15)+arrow('M350 440 Q330 485 290 515',p,.15)
   + arrow('M710 445 Q730 485 780 515',p,.15)+arrow('M850 440 Q830 485 790 515',p,.15)
   + appear(p,.28,agent(285,560,45,'fix')+agent(785,560,45,'fix'))
   + appear(p,.42,allowance(220,660,spentLeft)+allowance(720,660,spentRight))
   + appear(p,.58,label(285,730,followup?'revise work now':'two returns remain',25,C.navy)
     +label(785,730,followup?'handoff notes now':'one return remains',25,followup?C.red:C.navy))
   + today(followup?'after one more return, the right side reaches its limit':'two items consume two of the three returns');
}
S.r19 = p => countChoice(p,false);
S.r20 = p => countChoice(p,true);

S.r21 = p => open(2,'A forbidden action is refused',C.pink)
 + appear(p,.0,agent(200,350,65,'fix',{main:true})+label(200,475,'main fixer',28))
 + appear(p,.13,doc(410,250,250,200,{title:'use replaced agent'}))
 + arrow('M280 350 L390 350',p,.12)
 + arrow('M680 350 L785 350',p,.3)
 + appear(p,.34,agent(885,350,65,'fix',{ghost:true})+label(885,475,'replaced',27,C.grey))
 + cross(740,350,75,C.red,ease((p-.45)/.13))
 + appear(p,.6,doc(420,545,200,140,{title:'stored item'})+label(540,740,'item stays unchanged',29))
 + today('reject this attempt; pause the work');

S.r22 = p => open(2,'Keep the build’s failure response?',C.pink)
 + appear(p,.0,doc(100,300,175,205,{title:'refused action'}))
 + arrow('M295 405 L410 405',p,.10)
 + appear(p,.19,clock(485,405,65)+label(485,535,'pause',30))
 + arrow('M565 405 L680 405',p,.30)
 + appear(p,.40,phone(740,240,235,350).replace('Telegram','Notification')+bubble(765,370,185,85,['Work paused'],{size:23}))
 + arrow('M840 615 C840 730 290 730 210 555',p,.53)
 + appear(p,.66,agent(490,680,45,'fix',{main:true})+label(490,758,'next scheduled check',24))
 + today('notify you, then retry with the same agents');

S.r23 = p => open(3,'GitHub changed after review',C.sky)
 + appear(p,.0,label(540,250,'GitHub = the shared code',27,C.navy))
 + line('M150 355 L930 355',ease((p-.04)/.35),{width:8})
 + appear(p,.12,`<circle cx="330" cy="355" r="28" fill="${C.paper}" stroke="${C.ink}" stroke-width="4"/>`+label(330,445,'reviewed version',27))
 + appear(p,.3,`<circle cx="850" cy="355" r="28" fill="${C.mustard}" stroke="${C.ink}" stroke-width="4"/>`+label(850,445,'new version',27))
 + appear(p,.22,doc(220,510,215,200,{title:'old approved patch',diff:true}))
 + arrow('M465 595 L760 595',p,.44)
 + cross(850,595,100,C.red,ease((p-.59)/.13))
 + today('old patch cannot publish onto the changed version');

S.r24 = p => open(3,'Approve this way to continue?',C.sky)
 + appear(p,.0,box3d(110,500,160,200,{face:C.lightGreen,label:'updated copy'}))
 + arrow('M305 410 L405 410',p,.10)
 + appear(p,.20,agent(485,410,60,'fix',{main:true})+label(485,540,'decide next work',24))
 + arrow('M560 410 L650 410',p,.31)
 + appear(p,.40,doc(680,310,175,195,{title:'new product patch',diff:true}))
 + arrow('M765 525 Q765 650 630 650',p,.53)
 + appear(p,.61,agent(535,650,50,'rev')+label(535,744,'new review',24))
 + arrow('M470 650 L345 650',p,.67)
 + appear(p,.75,chip(100,620,230,'new push tap',C.green,26,C.paper))
 + today('update copy; resume the main fixer; require fresh approval');

S.r25 = p => open(4,'How can obsolete work close?',C.pink)
 + appear(p,.0,bubble(90,210,360,110,['We no longer need this.'],{size:26,fill:C.lightGreen}))
 + appear(p,.12,doc(120,385,205,220,{title:'held work'})+tinyQuestion(165,635))
 + cross(220,675,65,C.red,ease((p-.25)/.13))
 + appear(p,.32,label(450,630,'question withdrawn',24,C.navy))
 + arrow('M350 470 L660 470',p,.41)
 + appear(p,.49,label(500,415,'later release',26,C.red))
 + appear(p,.57,phone(710,250,260,475)+bubble(735,390,210,120,['Same question','appears again'],{size:24}))
 + today('withdrawal can leave the held item open');

S.r26 = p => open(4,'Two ways to close it immediately')
 + label(285,245,'ADD A DROP ACTION',27,C.navy)+label(795,245,'EXTEND WITHDRAWAL',27,C.navy)
 + appear(p,.0,doc(130,290,120,145,{title:'patch',diff:true})+tinyQuestion(290,315)+tinyQuestion(675,315)+doc(850,290,120,145,{title:'patch',diff:true}))
 + arrow('M190 450 Q190 505 250 540',p,.15)+arrow('M350 430 Q350 505 300 540',p,.15)
 + arrow('M730 430 L730 540',p,.27)
 + arrow('M910 450 L910 515',p,.31)
 + appear(p,.36,closed(180,550,220)+closed(635,550,190))
 + appear(p,.48,clock(910,570,40)+label(910,645,'still held',20))
 + appear(p,.62,label(285,730,'no push · no return used',23,C.navy)+label(790,730,'questions close; patches need a rule',20,C.navy))
 + today('withdrawal does not reliably close its held item');

S.r27 = p => open(4,'Close old waits at the next run')
 + appear(p,.0,doc(100,290,145,190,{title:'held patch',diff:true})+doc(280,290,145,190,{title:'held question'}))
 + appear(p,.15,`<rect x="485" y="280" width="22" height="435" fill="${C.navy}"/>`+label(495,250,'new run',28,C.navy))
 + arrow('M175 500 Q175 530 250 565',p,.23)+arrow('M350 500 Q350 530 280 565',p,.23)
 + appear(p,.33,closed(150,580,235))
 + arrow('M435 365 L650 365',p,.40)
 + appear(p,.5,doc(685,270,170,185,{title:'notes + files'}))
 + arrow('M770 480 L770 550',p,.6)
 + appear(p,.68,agent(770,625,60,'fix',{fresh:true})+label(770,735,'reconsider as new work',25))
 + today('a new delegate can replace one old item; no general closure rule');

S.r28 = p => panel(C.navy)+heading('READY FOR YOUR DECISIONS',C.paper)
 + title('One job, two teams',185,72,C.paper)
 + appear(p,.0,doc(120,270,205,240,{title:'your rules'}))
 + appear(p,.13,agent(540,375,78,'fix',{main:true})+`<circle cx="850" cy="375" r="101" fill="${C.paper}"/>`+agent(850,375,78,'rev',{main:true}))
 + arrow('M350 390 L435 390',p,.26,C.paper)
 + appear(p,.40,phone(400,525,300,215)+chip(430,625,240,'Start trial?',C.mustard,29))
 + appear(p,.61,label(190,650,'still off',31,C.paper)+label(870,650,'your choice',29,C.paper))
 + appear(p,.77,label(540,815,'SVG animation · ElevenLabs narration',23,C.paper));
