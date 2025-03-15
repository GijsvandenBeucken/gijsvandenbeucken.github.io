// JavaScript voor de gecombineerde BurgerConnect Demo

// We hebben in totaal 11 stappen in je gecombineerde HTML.
const demoConfig = {
    totalSteps: 12
  };
  
  let currentStep = 1;      // Houd de huidige stap bij
  let callInterval = null;  // Voor de gesprekstimer
  let callSeconds = 0;      // Seconden van het gesprek
  
  document.addEventListener('DOMContentLoaded', () => {
    // Verberg eerst alle steps en toon alleen stap 1
    showStep(currentStep);
  
    // --- ALGEMENE NEXT/PREV KNOPPEN ---
    document.addEventListener('click', (e) => {
      // "Volgende stap" knop
      if (
        e.target.classList.contains('next') ||
        (e.target.parentElement && e.target.parentElement.classList.contains('next'))
      ) {
        goToStep(currentStep + 1);
      }
      // "Vorige stap" knop
      else if (
        e.target.classList.contains('prev') ||
        (e.target.parentElement && e.target.parentElement.classList.contains('prev'))
      ) {
        goToStep(currentStep - 1);
      }
    });

     //  Intro-afbeelding (stap 1) klik-handler
     const step1IntroDiv = document.getElementById('step1-intro');
     if (step1IntroDiv) {
       step1IntroDiv.addEventListener('click', () => {
         // Verberg het intro-div
         step1IntroDiv.style.display = 'none';
         // Toon de normale content
         document.getElementById('step1-actual').style.display = 'block';
       });
     }
  
    // --- CHAT-FLOW (stappen 1 t/m 5) ---
    // 1. Als je op het document-link klikt in de chat (stap 2), ga je naar het formulier (stap 3).
    const documentLink = document.getElementById('document-link');
    if (documentLink) {
      documentLink.addEventListener('click', () => {
        goToStep(3);
      });
    }
  
    // 2. "Terug" vanuit het formulier (stap 3) keert terug naar chat (stap 2).
    const backToChat = document.getElementById('back-to-chat');
    if (backToChat) {
      backToChat.addEventListener('click', () => {
        goToStep(2);
      });
    }
  
    // 3. "Verzenden" formulier (stap 3) -> meldingen (stap 4).
    const submitForm = document.getElementById('submit-form');
    if (submitForm) {
      submitForm.addEventListener('click', () => {
        goToStep(4);
      });
    }
  
    // 4. In stap 1 (contact opnemen) kies je “Chatten” of “Bellen”; als de gebruiker op “Doorgaan” drukt,
    //    gaan we (in deze demo) standaard naar stap 2 (chat-flow). Pas dit aan als je wilt dat het
    //    afhankelijk is van de gekozen optie.
    const contactContinueBtn = document.getElementById('contact-continue-btn');
    if (contactContinueBtn) {
      contactContinueBtn.addEventListener('click', () => {
        goToStep(2);
      });
    }

    const notifWijzigingEl = document.getElementById('notifAow');
if (notifWijzigingEl) {
  notifWijzigingEl.addEventListener('click', () => {
    // Ga naar de volgende stap
    goToStep(currentStep + 1);
  });
}
  
    // --- TELEFONIE-FLOW (stappen 6 t/m 11) ---
    // 1. Op stap 7 staat een “Belknop” die het gesprek start. We laten die direct naar stap 8 gaan.
    const phoneCallButton = document.getElementById('phone-call-button');
    if (phoneCallButton) {
      phoneCallButton.addEventListener('click', () => {
        goToStep(8);
      });
    }
  
    // 2. In stap 8 is er een “Doorgaan” knop (routing-continue) die direct naar stap 9 gaat (actief gesprek).
    const routingContinueButton = document.getElementById('routing-continue');
    if (routingContinueButton) {
      routingContinueButton.addEventListener('click', () => {
        goToStep(6);
      });
    }
  
    // 3. In stap 9 (actief gesprek) zien we soms een “call-avatar” die, als je erop klikt, door kan gaan naar stap 10.
    document.addEventListener('click', (e) => {
      if (e.target.closest('.call-avatar')) {
        // Als je op de headset/avatar klikt, bijvoorbeeld om te simuleren dat het gesprek naar
        // de medewerker-portal gaat, dan ga je naar stap 10.
        goToStep(10);
      }
    });

        // 2. In stap 8 is er een “Doorgaan” knop (routing-continue) die direct naar stap 9 gaat (actief gesprek).
        const routingContinueButton2 = document.getElementById('routing-continue2');
        if (routingContinueButton2) {
          routingContinueButton2.addEventListener('click', () => {
            goToStep(9);
          });
        }
  
  }); // end DOMContentLoaded
  
  
  // ----- FUNCTIES -----
  
  // Gaat naar een specifieke stap (mits binnen 1..11)
  function goToStep(stepNumber) {
    if (stepNumber >= 1 && stepNumber <= demoConfig.totalSteps) {
      currentStep = stepNumber;
      showStep(currentStep);
    }
  }
  
  // Laat alleen de gevraagde stap zien, verbergt alle andere
  function showStep(step) {
    // Verberg alle .step secties
    document.querySelectorAll('.step').forEach((section) => {
      section.style.display = 'none';
      section.classList.remove('active');
    });
  
    // Toon de gevraagde stap
    const stepToShow = document.getElementById(`step-${step}`);
    if (stepToShow) {
      stepToShow.style.display = 'block';
      stepToShow.classList.add('active');
    }
  
    // Start of stop de telefoontimer
    // We hebben besloten dat stap 9 de "actief gesprek" stap is.
    if (step === 9) {
      startCallTimer();
    } else {
      stopCallTimer();
    }

      // Voorbeeld: als stap 4 de “meldingen”-stap is, reset & toon notificaties
  if (step === 4) {
    // Zorg dat de elementen in de HTML id="notifWijziging" en id="notifAow" hebben
    const notifWijziging = document.getElementById('notifWijziging');
    const notifAow = document.getElementById('notifAow');

    if (notifWijziging && notifAow) {
      // 1) Reset naar verborgen toestand
      //    - Als je CSS-animaties gebruikt (b.v. .popup-notif.show), dan remove je 'show'
      notifWijziging.classList.remove('show');
      notifAow.classList.remove('show');
      
      // 2) Eventueel direct verbergen met display=none
      // notifWijziging.style.display = 'none';
      // notifAow.style.display = 'none';

      // 3) Na korte delay eerst de wijzigingsmelding tonen
      setTimeout(() => {
        // Als je .popup-notif en .show gebruikt:
        notifWijziging.classList.add('show');

        // Of, zonder animatie:  notifWijziging.style.display = 'block';
      }, 500);

      // 4) Dan 5 seconden later de AOW-melding
      setTimeout(() => {
        notifAow.classList.add('show');
        // Of: notifAow.style.display = 'block';
      }, 5500);
    }
  }
  
    // Werk de zichtbaarheid van de prev/next knoppen bij
    toggleButtons();

  
  }
  
  // Logica voor het tonen/verbergen van de "Vorige stap" en "Volgende stap" knoppen
  function toggleButtons() {
    // Vorige-knop verbergen als we in stap 1 zitten
    const prevButton = document.querySelector(`#step-${currentStep} .prev`);
    if (currentStep === 1 && prevButton) {
      prevButton.style.display = 'none';
    } else if (prevButton) {
      prevButton.style.display = 'inline-block';
    }
  
    // Volgende-knop verbergen als we op de allerlaatste stap zijn (stap 11)
    const nextButton = document.querySelector(`#step-${currentStep} .next`);
    if (currentStep === demoConfig.totalSteps && nextButton) {
      nextButton.style.display = 'none';
    } else if (nextButton) {
      nextButton.style.display = 'inline-block';
    }
  }
  
  // --- Timer-functies voor het telefoongesprek ---
  
  function startCallTimer() {
    callSeconds = 0; // reset teller
  
    // Eventueel een lopende interval eerst stopzetten
    if (callInterval) {
      clearInterval(callInterval);
    }
    // Direct updaten
    updateCallTimerDisplay();
  
    // Elke seconde ophogen
    callInterval = setInterval(() => {
      callSeconds++;
      updateCallTimerDisplay();
    }, 1000);
  }
  
  function stopCallTimer() {
    if (callInterval) {
      clearInterval(callInterval);
      callInterval = null;
    }
  }
  
  function updateCallTimerDisplay() {
    const minutes = Math.floor(callSeconds / 60);
    const seconds = callSeconds % 60;
    const formattedTime =
      String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
  
    // In jouw HTML is stap 9 de actieve-gesprek-stap (call-screen).
    // Daar zit een element met class "call-timer".
    const stepNineTimer = document.querySelector('#step-9 .call-timer');
    if (stepNineTimer) {
      stepNineTimer.textContent = formattedTime;
    }
  }
  
  // Zorg dat wanneer de gebruiker met de browser-terugknop hier komt (page cache),
  // de pagina vers herlaadt (voorkomt rare weergave)
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });
