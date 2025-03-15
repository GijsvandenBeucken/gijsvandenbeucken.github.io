// JavaScript voor BurgerConnect Demo
const demoConfig = {
    totalSteps: 6 // Aangepast naar 5 stappen voor de BurgerConnect demo
};

let currentStep = 1; // Houd de huidige stap bij
let callInterval; // Voor de gesprekstimer
let callSeconds = 0; // Seconden van het gesprek

// Zorg ervoor dat de juiste secties worden getoond wanneer de DOM geladen is
document.addEventListener('DOMContentLoaded', () => {
    const totalSteps = demoConfig.totalSteps;
    
    // Verberg alle stappen boven het totale aantal
    for (let i = totalSteps + 1; i <= 8; i++) {
        const stepElement = document.getElementById(`step-${i}`);
        if (stepElement) {  
            stepElement.style.display = 'none';
        }
    }

    // Toon de eerste stap
    showStep(currentStep);

    // Voeg eventlisteners toe aan de knoppen voor 'Volgende' en 'Terug'
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('next') || e.target.parentElement.classList.contains('next')) {
            goToStep(currentStep + 1);
        } else if (e.target.classList.contains('prev') || e.target.parentElement.classList.contains('prev')) {
            goToStep(currentStep - 1);
        }
    });

    // Voeg eventlistener toe voor het selecteren van opties
    document.querySelectorAll('.option-card').forEach(card => {
        card.addEventListener('click', () => {
            // Verwijder selected class van alle cards in dezelfde routing-options groep
            const parentGroup = card.closest('.routing-options');
            if (parentGroup) {
                parentGroup.querySelectorAll('.option-card').forEach(c => {
                    c.classList.remove('selected');
                });
            }
            // Voeg selected toe aan de aangeklikte card
            card.classList.add('selected');
        });
    });
    
    // Voeg eventlisteners toe voor extra navigatie-opties
    const phoneCallButton = document.getElementById('phone-call-button');
    if (phoneCallButton) {
        phoneCallButton.addEventListener('click', () => {
            goToStep(3);
        });
    }
    
    const routingContinueButton = document.getElementById('routing-continue');
    if (routingContinueButton) {
        routingContinueButton.addEventListener('click', () => {
            goToStep(4);
        });
    }
    
    const contactContinueButton = document.querySelector('.contact-continue');
    if (contactContinueButton) {
        contactContinueButton.addEventListener('click', () => {
            goToStep(2);
        });
    }
    
    // Voeg eventlistener toe voor de call-avatar
    document.addEventListener('click', (e) => {
        if (e.target.closest('.call-avatar')) {
            goToStep(5);
        }
    });
});

function goToStep(step) {
    if (step > 0 && step <= demoConfig.totalSteps) {
        currentStep = step;
        showStep(currentStep);
    }
}

function showStep(step) {
    // Verberg alle stappen
    document.querySelectorAll('.step').forEach((section) => {
        section.classList.remove('active');
        section.style.display = 'none'; // Verberg alle secties
    });

    // Toon de juiste stap
    const stepToShow = document.getElementById(`step-${step}`);
    if (stepToShow) {
        stepToShow.classList.add('active');
        stepToShow.style.display = 'block'; // Toon als block display
    }
    
    // Start of stop de timer afhankelijk van de stap
    if (step === 4) {
        startCallTimer();
    } else {
        stopCallTimer();
    }

    // Pas de knoppenlogica aan
    toggleButtons();
}

function toggleButtons() {
    // Verberg de 'Terug'-knop bij de eerste stap
    const prevButton = document.querySelector(`#step-${currentStep} .prev`);
    if (currentStep === 1 && prevButton) {
        prevButton.style.display = 'none';
    } else if (prevButton) {
        prevButton.style.display = 'inline-block';
    }

    // Verberg de 'Volgende'-knop bij de laatste stap
    const nextButton = document.querySelector(`#step-${currentStep} .next`);
    
    if (currentStep === demoConfig.totalSteps) {
        if (nextButton) {
            nextButton.style.display = 'none'; // Verberg de 'Volgende'-knop
        }
    } else if (nextButton) {
        nextButton.style.display = 'inline-block'; // Toon de 'Volgende'-knop indien niet op de laatste stap
    }
}

// Controleer of de pagina via de terugknop van de browser is bezocht
window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        // Als de pagina uit de cache is geladen, forceer dan een herlaad
        window.location.reload();
    }
});

// Functie om de timer te starten
function startCallTimer() {
    // Reset de timer
    callSeconds = 0;
    
    // Stop een eventueel bestaande interval
    if (callInterval) {
        clearInterval(callInterval);
    }
    
    // Update de timer direct
    updateCallTimerDisplay();
    
    // Start een nieuwe interval
    callInterval = setInterval(function() {
        callSeconds++;
        updateCallTimerDisplay();
    }, 1000);
}

// Functie om de timer te stoppen
function stopCallTimer() {
    if (callInterval) {
        clearInterval(callInterval);
        callInterval = null;
    }
}

// Functie om de timerweergave bij te werken
function updateCallTimerDisplay() {
    const minutes = Math.floor(callSeconds / 60);
    const seconds = callSeconds % 60;
    const formattedTime = minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
    
    // Update stap 4 timer
    const stepFourTimer = document.querySelector('#step-4 .call-timer');
    if (stepFourTimer) {
        stepFourTimer.textContent = formattedTime;
    }
}