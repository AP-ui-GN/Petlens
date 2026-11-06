import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Check, CircleAlert, Plus, Save, Trash2 } from 'lucide-react';
import { petFormIsValid, validatePetForm, type PetFormErrors } from '@/lib/pet-form';
import { type Pet } from '@/lib/storage';

const ElectricLogo = lazy(() => import('@/components/ElectricLogo'));

type Props = {
  pets: Pet[];
  addPet: (pet: Omit<Pet, 'id' | 'createdAt'>) => Pet;
  updatePet: (id: string, pet: Omit<Pet, 'id' | 'createdAt'>) => void;
  deletePet: (id: string) => void;
};
type FormState = Omit<Pet, 'id' | 'createdAt'>;
const blank: FormState = { name: '', species: 'Dog', breed: '', age: '', weight: '', weightUnit: 'lb', notes: '' };
export default function PetProfile({ pets, addPet, updatePet, deletePet }: Props) {
  const [selectedId, setSelectedId] = useState(pets[0]?.id ?? 'new');
  const [form, setForm] = useState<FormState>(pets[0] ? { ...pets[0] } : blank);
  const [saved, setSaved] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const skipReset = useRef(false);
  const selectedPet = pets.find((pet) => pet.id === selectedId);
  const validated = validatePetForm(form);
  const errors: PetFormErrors = {
    ...(attempted ? validated : {}),
    ...(validated.age ? { age: validated.age } : {}),
    ...(validated.weight ? { weight: validated.weight } : {}),
  };

  useEffect(() => {
    // Creating a pet changes the selection. Keep the form and the saved note
    // from that submit instead of clearing them.
    if (skipReset.current) {
      skipReset.current = false;
      return;
    }
    setForm(selectedPet ? { ...selectedPet } : blank);
    setSaved(false);
    setAttempted(false);
  }, [selectedId]); // selection is the intentional edit boundary

  const update = (key: Exclude<keyof FormState, 'weightUnit'>, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setSaved(false);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const next = validatePetForm(form);
    setAttempted(true);
    if (!petFormIsValid(next)) {
      setSaved(false);
      return;
    }
    if (selectedPet) updatePet(selectedPet.id, form);
    else {
      const created = addPet(form);
      skipReset.current = true;
      setSelectedId(created.id);
      setForm({ ...form });
    }
    setSaved(true);
  };

  const removeSelectedPet = () => {
    if (!selectedPet) return;
    const confirmed = window.confirm(
      `Are you sure you want to delete ${selectedPet.name}? All data associated with this pet, including their profile, saved walks, cognitive checks, and happiness entries, will be permanently deleted. This cannot be undone.`,
    );
    if (!confirmed) return;
    deletePet(selectedPet.id);
    setSelectedId('new');
    setForm(blank);
    setSaved(false);
    setAttempted(false);
  };

  return (
    <div className="page-frame max-w-5xl">
      <div className="stagger">
        <div className="flex items-center justify-between gap-5">
          <h1 className="display-title text-3xl sm:text-5xl">New <span className="text-petlens-trim">Profile</span></h1>
          <div className="h-20 w-20 shrink-0 sm:h-32 sm:w-44" aria-hidden="true">
            <Suspense fallback={null}>
              <ElectricLogo
                src={`${import.meta.env.BASE_URL}gold-hexagonal-petlens-logo-Photoroom.png`}
                color="#553b00"
                glowColor="#9a6b00"
                glow={0.7}
                speed={1.4}
                interactive={false}
                theme="light"
              />
            </Suspense>
          </div>
        </div>
      </div>

      {pets.length > 0 && (
        <div className="panel panel-padded mt-9 stagger-2">
          <div className="flex flex-wrap justify-between items-center gap-4">
            <div><div className="eyebrow">Profiles on this device</div><h2 className="display-title text-2xl mt-2">Choose a pet to edit</h2></div>
            <button className="btn-secondary" onClick={() => setSelectedId('new')} data-testid="button-add-pet"><Plus size={15} /> Add pet</button>
          </div>
          <div className="flex flex-wrap gap-3 mt-6">
            {pets.map((pet) => <button className={`flex items-center gap-3 rounded-xl border p-3 text-left transition ${selectedId === pet.id ? 'border-petlens-trim/60 bg-petlens-azure/20 ring-2 ring-petlens-trim/60' : 'bg-transparent'}`} style={selectedId === pet.id ? { boxShadow: '0 0 15px color-mix(in srgb, var(--color-petlens-trim) 35%, transparent)' } : undefined} onClick={() => setSelectedId(pet.id)} key={pet.id} data-testid={`button-select-pet-${pet.id}`}><span className="pet-orb" style={{ width: 42, height: 42, borderRadius: 15, fontSize: 14 }}>{pet.name.slice(0, 2).toUpperCase()}</span><span><span className="font-bold text-sm block">{pet.name}</span><span className="body-muted text-xs block mt-1">{pet.breed || pet.species}</span></span>{selectedId === pet.id && <Check size={15} style={{ color: 'var(--color-petlens-trim)' }} />}</button>)}
          </div>
        </div>
      )}

      <form onSubmit={submit} noValidate className="mt-5 stagger-3">
        <div className="panel panel-padded">
          <div className="grid sm:grid-cols-2 gap-5">
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="pet-name">Name <span className="text-petlens-emerald">*</span></label>
              <input id="pet-name" className="field-input" value={form.name} onChange={(event) => update('name', event.target.value)} aria-invalid={errors.name ? true : undefined} aria-describedby={errors.name ? 'pet-name-error' : undefined} data-testid="input-pet-name" />
              {errors.name && <p id="pet-name-error" className="text-status-error text-sm mt-2 flex items-center gap-2" role="alert" data-testid="text-pet-name-error"><CircleAlert size={15} />{errors.name}</p>}
            </div>
            <div><label className="field-label" htmlFor="pet-species">Species</label><select id="pet-species" className="field-input" value={form.species} onChange={(event) => update('species', event.target.value)} data-testid="select-pet-species"><option>Dog</option><option>Cat</option><option>Other</option></select></div>
            <div><label className="field-label" htmlFor="pet-breed">Breed</label><input id="pet-breed" className="field-input" value={form.breed} onChange={(event) => update('breed', event.target.value)} placeholder="Optional" data-testid="input-pet-breed" /></div>
            <div>
              <label className="field-label" htmlFor="pet-age">Age <span className="body-muted font-normal">(years)</span></label>
              <input id="pet-age" className="field-input" inputMode="decimal" value={form.age} onChange={(event) => update('age', event.target.value)} aria-invalid={errors.age ? true : undefined} aria-describedby={errors.age ? 'pet-age-error' : undefined} data-testid="input-pet-age" />
              {errors.age && <p id="pet-age-error" className="text-status-error text-sm mt-2 flex items-center gap-2" role="alert" data-testid="text-pet-age-error"><CircleAlert size={15} />{errors.age}</p>}
            </div>
            <div>
              <label className="field-label" htmlFor="pet-weight">Weight <span className="body-muted font-normal">(lb)</span></label>
              <input id="pet-weight" className="field-input" inputMode="decimal" value={form.weight} onChange={(event) => update('weight', event.target.value)} aria-invalid={errors.weight ? true : undefined} aria-describedby={errors.weight ? 'pet-weight-error' : undefined} data-testid="input-pet-weight" />
              {errors.weight && <p id="pet-weight-error" className="text-status-error text-sm mt-2 flex items-center gap-2" role="alert" data-testid="text-pet-weight-error"><CircleAlert size={15} />{errors.weight}</p>}
            </div>
            <div className="sm:col-span-2"><label className="field-label" htmlFor="pet-notes">Notes</label><textarea id="pet-notes" className="field-input min-h-28 resize-y" value={form.notes} onChange={(event) => update('notes', event.target.value)} data-testid="textarea-pet-notes" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-7 pt-5 border-t">
            <div className="flex flex-wrap items-center justify-end gap-3">
              {saved && <span className="text-status-success text-xs font-semibold flex items-center gap-1"><Check size={14} /> Saved locally</span>}
              {selectedPet && (
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-full bg-status-danger px-5 py-3 text-sm font-bold text-white transition hover:brightness-110"
                  onClick={removeSelectedPet}
                  data-testid="button-delete-pet"
                >
                  <Trash2 size={15} /> Delete pet
                </button>
              )}
              <button type="submit" className="btn-primary" data-testid="button-save-pet"><Save size={15} /> Save profile</button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}