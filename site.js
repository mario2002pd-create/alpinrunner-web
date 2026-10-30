(function(){
  document.documentElement.classList.add('js');

  // mobile menu
  var b=document.getElementById('burger'),m=document.getElementById('menu');
  if(b&&m)b.addEventListener('click',function(){var o=m.classList.toggle('open');b.setAttribute('aria-expanded',o)});

  // scroll reveal
  var els=[].slice.call(document.querySelectorAll('.rv'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(e){e.forEach(function(x){if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},{threshold:.1});
    els.forEach(function(el){io.observe(el)});
    setTimeout(function(){els.forEach(function(el){el.classList.add('in')})},4000);
  }else{els.forEach(function(el){el.classList.add('in')})}

  // home slider
  var sl=document.getElementById('slider');
  if(sl){
    var im=[].slice.call(sl.querySelectorAll('img')),k=0;
    if(im.length>1)setInterval(function(){im[k].classList.remove('on');k=(k+1)%im.length;im[k].classList.add('on')},5000);
  }

  // home: upcoming events from the full agenda, always relative to today
  var ev=window.AR_EVENTS,rows=document.getElementById('home-rows');
  if(ev&&rows){
    var DAYS=['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'],MON=['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];
    var t=new Date();var iso=t.getFullYear()+'-'+('0'+(t.getMonth()+1)).slice(-2)+'-'+('0'+t.getDate()).slice(-2);
    var up=ev.filter(function(e){return e.d>=iso}).sort(function(a,b){return a.d<b.d?-1:1});
    if(up.length){
      rows.innerHTML=up.slice(0,3).map(function(e){
        var d=new Date(e.d+'T12:00:00');
        return '<a class="row-ev" href="'+e.u+'"><div class="d">'+('0'+d.getDate()).slice(-2)+'. '+MON[d.getMonth()]+'<small>'+DAYS[d.getDay()]+'</small></div><div><h3></h3></div><span class="go" aria-hidden="true">→</span></a>';
      }).join('');
      [].slice.call(rows.querySelectorAll('h3')).forEach(function(h,i){h.textContent=up[i].t});
      var n=document.getElementById('next-ev');
      if(n){var d0=new Date(up[0].d+'T12:00:00');n.href=up[0].u;n.innerHTML='<b>Nächster Termin · '+d0.getDate()+'. '+MON[d0.getMonth()]+'</b> ';n.appendChild(document.createTextNode(up[0].t+' → Details'))}
    }
  }

  // lightbox
  document.addEventListener('click',function(e){
    var a=e.target.closest&&e.target.closest('a[data-lightbox]');
    if(!a||!/\.(jpe?g|png|gif|webp)(\?|$)/i.test(a.getAttribute('href')))return;
    e.preventDefault();
    var o=document.createElement('div');o.className='lb';o.setAttribute('role','dialog');
    o.innerHTML='<img alt=""><button type="button">Schliessen</button>';
    o.querySelector('img').src=a.href;
    var close=function(){o.remove();document.removeEventListener('keydown',kd)};
    var kd=function(ev2){if(ev2.key==='Escape')close()};
    o.addEventListener('click',close);document.addEventListener('keydown',kd);
    document.body.appendChild(o);o.querySelector('button').focus();
  });

  // routes database: filters + progressive reveal
  var box=document.getElementById('routes');
  if(box){
    var cards=[].slice.call(box.children),shown=40,F={art:'',reg:'',kat:'',dist:'',year:'',q:''};
    var count=document.getElementById('f-count'),more=document.getElementById('f-more');
    function apply(){
      var n=0,vis=0;
      cards.forEach(function(c){
        var ok=(!F.art||c.dataset.art===F.art)&&(!F.reg||c.dataset.reg===F.reg)&&(!F.kat||c.dataset.kat===F.kat)&&(!F.dist||c.dataset.dist===F.dist)&&(!F.year||c.dataset.year===F.year)&&(!F.q||c.dataset.q.indexOf(F.q)>-1);
        if(ok){n++;c.hidden=n>shown;if(n<=shown)vis++}else c.hidden=true;
      });
      count.textContent='Es wurden '+n+' Einträge gefunden.';
      more.hidden=n<=shown;
    }
    [].slice.call(document.querySelectorAll('[data-f]')).forEach(function(s){s.addEventListener('change',function(){F[s.dataset.f]=s.value;shown=40;apply()})});
    document.getElementById('f-q').addEventListener('input',function(e){F.q=e.target.value.trim().toLowerCase();shown=40;apply()});
    document.getElementById('f-reset').addEventListener('click',function(){
      F={art:'',reg:'',kat:'',dist:'',year:'',q:''};
      [].slice.call(document.querySelectorAll('[data-f]')).forEach(function(s){s.value=''});
      document.getElementById('f-q').value='';shown=40;apply();
    });
    more.addEventListener('click',function(){shown+=40;apply()});
    apply();
  }
})();
