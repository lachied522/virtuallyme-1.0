function popupOpen(popupWrapper) {
    const popup = popupWrapper.querySelector('.popup');
  
    // set initial state
    popupWrapper.style.opacity = '0';
    popup.style.transform = 'scale(0.6)';
    
    // show popup wrapper
    popupWrapper.style.display = 'flex';
  
    // animate popup wrapper
    popup.animate([
      { transform: 'scale(0.6)' },
      { transform: 'scale(1.0)' },
    ], {
      duration: 300,
      easing: 'ease'
    });

    popupWrapper.animate([
        { opacity: '0' },
        { opacity: '1'}
      ], {
        duration: 200,
        easing: 'ease'
    });
  
    // set final state
    popupWrapper.style.opacity = '1';
    popup.style.transform = 'scale(1.0)';

}

function popupClose(popupWrapper) {
    const popup = popupWrapper.querySelector('.popup');
  
    popup.animate([
      { transform: 'scale(1.0)' },
      { transform: 'scale(0.6)' }
    ], {
      duration: 300,
      easing: 'ease'
    });

    popupWrapper.animate([
        { opacity: '1' },
        { opacity: '0' }
      ], {
        duration: 200,
        easing: 'ease'
    });
    
    // set final state
    popupWrapper.style.display = 'none';
    popupWrapper.style.opacity = '0';
    popup.style.transform = 'scale(0.6)';

}

function removeSampleConfirm(sampleWrapper){
    sampleWrapper.querySelector(".btn-secondary remove").style.display = 'none';
    sampleWrapper.querySelector(".btn-secondary confirm").style.display = 'flex';
    sampleWrapper.querySelector(".text-200").style.display = 'block';
}