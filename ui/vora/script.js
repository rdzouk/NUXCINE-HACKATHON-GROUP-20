// petit script pour simuler l'ouverture/fermeture du bottom-sheet
(function(){
  const sheet = document.getElementById('sheet');
  let open = true;

  // toggler en cliquant sur grabber
  const grabber = document.querySelector('.sheet-grabber');
  grabber.addEventListener('click', () => {
    toggleSheet();
  });

  function toggleSheet(){
    if(open){
      sheet.style.transform = 'translateY(56%)';
    } else {
      sheet.style.transform = 'translateY(0)';
    }
    open = !open;
  }

  // petit helper: basculer avec swipe up/down (mobile)
  let startY = null;
  sheet.addEventListener('touchstart', (e)=>{
    startY = e.touches[0].clientY;
  });
  sheet.addEventListener('touchend', (e)=>{
    if(startY === null) return;
    const endY = e.changedTouches[0].clientY;
    const dy = endY - startY;
    if(dy > 40) { // swipe down
      sheet.style.transform = 'translateY(56%)';
      open = false;
    } else if(dy < -40) { // swipe up
      sheet.style.transform = 'translateY(0)';
      open = true;
    }
    startY = null;
  });

})();
