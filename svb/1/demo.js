// JavaScript voor BurgerConnect Demo
const demoConfig = {
    totalSteps: 6 // Aangepast naar 6 stappen voor de BurgerConnect demo
};

let currentStep = 1; // Houd de huidige stap bij

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
    const chatOption = document.getElementById('chat-option');
    if (chatOption) {
        chatOption.addEventListener('click', () => {
            document.querySelectorAll('.contact-option').forEach(option => {
                option.classList.remove('selected');
            });
            chatOption.classList.add('selected');
        });
    }
    
    const contactContinueBtn = document.getElementById('contact-continue-btn');
    if (contactContinueBtn) {
        contactContinueBtn.addEventListener('click', () => {
            goToStep(2);
        });
    }
    
    const documentLink = document.getElementById('document-link');
    if (documentLink) {
        documentLink.addEventListener('click', () => {
            goToStep(3);
        });
    }
    
    const backToChat = document.getElementById('back-to-chat');
    if (backToChat) {
        backToChat.addEventListener('click', () => {
            goToStep(2);
        });
    }
    
    const submitForm = document.getElementById('submit-form');
    if (submitForm) {
        submitForm.addEventListener('click', () => {
            goToStep(4);
        });
    }
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
        stepToShow.style.display = 'block'; // Toon alleen de actieve sectie
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