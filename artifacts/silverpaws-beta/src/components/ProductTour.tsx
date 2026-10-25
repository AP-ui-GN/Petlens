import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

type ProductTourProps = {
  onComplete: () => void;
  onStepChange?: (step: number) => void;
  initialStep?: number;
};

type TargetRect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

const TOUR_STEPS = [
  {
    targetId: 'try-sample-btn',
    title: 'Try a sample walk',
    description: "Click 'Try Sample Dog Walk' below to run a simulated gait analysis.",
  },
  {
    targetId: 'movenet-card',
    title: 'Pose keypoints',
    description: 'The pose head marks the joints it outputs. This checkpoint uses 17 COCO joint names. The base of the tail is not one of them.',
  },
  {
    targetId: 'factor-scores',
    title: 'Gait scores',
    description: 'Scores summarize the available measurements. Pose-dependent factors are only shown when the clip supports them.'
  },
  {
    targetId: 'vet-summary-export',
    title: 'Vet PDF & care',
    description: 'Export a movement-observation report to discuss with your veterinarian, or find physical therapy specialists nearby.'
  },
];

const SPOTLIGHT_PADDING = 8;

export default function ProductTour({ onComplete, onStepChange, initialStep = 0 }: ProductTourProps) {
  const [currentStep, setCurrentStep] = useState(() =>
    Math.max(0, Math.min(TOUR_STEPS.length - 1, initialStep)),
  );
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const step = TOUR_STEPS[currentStep];

  useEffect(() => {
    let animationFrame = 0;
    const targetElement = document.getElementById(step.targetId);
    const originalScrollMargins = targetElement
      ? {
          top: targetElement.style.scrollMarginTop,
          bottom: targetElement.style.scrollMarginBottom,
        }
      : null;

    const updateTargetRect = () => {
      animationFrame = 0;
      if (!targetElement) {
        setTargetRect(null);
        return;
      }

      const rect = targetElement.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        setTargetRect(null);
        return;
      }

      setTargetRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    };

    const scheduleTargetUpdate = () => {
      if (animationFrame) return;
      animationFrame = window.requestAnimationFrame(updateTargetRect);
    };

    if (targetElement) {
      targetElement.style.scrollMarginTop = '100px';
      targetElement.style.scrollMarginBottom = '220px';
      targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    scheduleTargetUpdate();
    window.addEventListener('scroll', scheduleTargetUpdate, true);
    window.addEventListener('resize', scheduleTargetUpdate);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener('scroll', scheduleTargetUpdate, true);
      window.removeEventListener('resize', scheduleTargetUpdate);
      if (targetElement && originalScrollMargins) {
        targetElement.style.scrollMarginTop = originalScrollMargins.top;
        targetElement.style.scrollMarginBottom = originalScrollMargins.bottom;
      }
    };
  }, [step.targetId]);

  const isLastStep = currentStep === TOUR_STEPS.length - 1;

  function goBack() {
    const nextStep = Math.max(0, currentStep - 1);
    setCurrentStep(nextStep);
    onStepChange?.(nextStep);
  }

  function goNext() {
    if (isLastStep) {
      onComplete();
      return;
    }
    const nextStep = Math.min(TOUR_STEPS.length - 1, currentStep + 1);
    setCurrentStep(nextStep);
    onStepChange?.(nextStep);
  }

  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[999999]" role="presentation">
      <svg
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 h-full w-full"
      >
        <defs>
          <mask
            id="product-tour-spotlight-mask"
            maskContentUnits="userSpaceOnUse"
            maskUnits="userSpaceOnUse"
          >
            <rect width="100%" height="100%" fill="white" />
            {targetRect && (
              <rect
                x={targetRect.left - SPOTLIGHT_PADDING}
                y={targetRect.top - SPOTLIGHT_PADDING}
                width={targetRect.width + SPOTLIGHT_PADDING * 2}
                height={targetRect.height + SPOTLIGHT_PADDING * 2}
                rx="12"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(0, 0, 0, 0.85)"
          mask="url(#product-tour-spotlight-mask)"
        />
        {targetRect && (
          <rect
            x={targetRect.left - SPOTLIGHT_PADDING}
            y={targetRect.top - SPOTLIGHT_PADDING}
            width={targetRect.width + SPOTLIGHT_PADDING * 2}
            height={targetRect.height + SPOTLIGHT_PADDING * 2}
            rx="12"
            fill="none"
            stroke="#5e17eb"
            strokeWidth="3"
            className={currentStep === 0 ? 'animate-pulse' : undefined}
            style={{ filter: 'drop-shadow(0 0 15px rgba(94,23,235,0.5))' }}
          />
        )}
      </svg>

      <section
        aria-describedby="product-tour-description"
        aria-labelledby="product-tour-title"
        aria-modal="true"
        className="pointer-events-auto fixed bottom-6 left-1/2 z-[1000000] w-[92vw] max-w-lg -translate-x-1/2 rounded-2xl border-2 border-[#5e17eb]/60 bg-[#061826]/95 p-5 text-white shadow-[0_10px_30px_rgba(10,66,103,0.4)] backdrop-blur-xl"
        role="dialog"
      >
        <div className="flex items-center justify-between gap-3">
          <span className="font-sans text-xs font-bold uppercase tracking-wider text-slate-400/90">
            Step {currentStep + 1} of {TOUR_STEPS.length}
          </span>
          <button
            className="rounded px-2 py-1 text-sm font-semibold text-slate-200 hover:bg-white/10 hover:text-white"
            onClick={onComplete}
            type="button"
          >
            Skip Tour
          </button>
        </div>
        <h2 className="mt-2 text-lg font-bold text-white" id="product-tour-title">
          {step.title}
        </h2>
        <p className="mt-1 mb-5 text-sm leading-relaxed text-slate-200" id="product-tour-description">
          {step.description}
        </p>

        <div className="flex items-center justify-between gap-3 border-t border-slate-700 pt-3">
          <button
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={currentStep === 0}
            onClick={goBack}
            type="button"
          >
            Back
          </button>
          <button
            className="rounded-lg bg-[#1669aa] px-5 py-2 text-sm font-bold text-white hover:brightness-110"
            onClick={goNext}
            type="button"
          >
            {isLastStep ? 'Finish' : 'Next'}
          </button>
        </div>
      </section>
    </div>,
    document.body,
  );
}
