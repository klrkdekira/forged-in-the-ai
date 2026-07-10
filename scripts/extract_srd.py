import json
import re
from pathlib import Path
import sys

# Add server to path so we can import the engine pack schemas
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
from engine.packs import ContentPack, SpecialAbility, Item, Reputation, Trauma, Vice, CrewUpgrade, PositionRoll, RollResult, HeatPenalty, EntanglementEntry

def extract_special_abilities(srd_text):
    abilities = []
    
    lines = srd_text.splitlines()
    in_ability = False
    current_name = ""
    current_desc = []
    
    def save_ability():
        if current_name and current_desc:
            _id = current_name.lower().replace(" ", "_").replace("'", "")
            desc_text = "\n".join(current_desc).strip()
            if not any(a.id == _id for a in abilities):
                abilities.append(SpecialAbility(
                    id=_id,
                    name=current_name.strip(),
                    description=desc_text,
                    tags=[]
                ))
    
    for i, line in enumerate(lines):
        line_num = i + 1
        is_in_range = (1060 <= line_num <= 1320) or (1619 <= line_num <= 1703)
        
        if is_in_range and line.startswith("### "):
            save_ability()
            current_name = line[4:].strip()
            current_desc = []
            in_ability = True
        elif line.startswith("## ") or line.startswith("# ") or not is_in_range:
            if in_ability:
                save_ability()
                in_ability = False
                current_name = ""
                current_desc = []
        elif in_ability:
            if line.strip() or current_desc:
                current_desc.append(line)
                
    if in_ability:
        save_ability()
            
    return abilities

def extract_traumas():
    return [
        Trauma(id="cold", name="Cold", description="Not moved by emotional appeals or social bonds."),
        Trauma(id="haunted", name="Haunted", description="Often lost in reverie, reliving past horrors, seeing things."),
        Trauma(id="obsessed", name="Obsessed", description="Enthralled by one thing: an activity, a person, an ideology."),
        Trauma(id="paranoid", name="Paranoid", description="Imagine danger everywhere; can't trust others."),
        Trauma(id="reckless", name="Reckless", description="Little regard for your own safety or best interests."),
        Trauma(id="soft", name="Soft", description="Lose your edge; become sentimental, passive, gentle."),
        Trauma(id="unstable", name="Unstable", description="Emotional state is volatile. Can instantly rage, or fall into despair, act impulsively, or freeze up."),
        Trauma(id="vicious", name="Vicious", description="Seek out opportunities to hurt people, even for no good reason."),
    ]

def extract_vices():
    return [
        Vice(id="faith", name="Faith", description="Dedicated to an unseen power, forgotten god, ancestor, etc."),
        Vice(id="gambling", name="Gambling", description="Crave games of chance, betting on sporting events, etc."),
        Vice(id="luxury", name="Luxury", description="Expensive or ostentatious displays of opulence."),
        Vice(id="obligation", name="Obligation", description="Devoted to a family, a cause, an organization, a charity, etc."),
        Vice(id="pleasure", name="Pleasure", description="Gratification from lovers, food, drink, drugs, art, theater, etc."),
        Vice(id="stupor", name="Stupor", description="Seek oblivion in the abuse of drugs, drinking to excess, getting beaten to a pulp in fighting pits, etc."),
        Vice(id="weird", name="Weird", description="Experiment with strange essences, consort with rogue spirits, observe bizarre rituals or taboos, etc."),
    ]

def extract_reputations():
    return [
        Reputation(id="ambitious", name="Ambitious"),
        Reputation(id="brutal", name="Brutal"),
        Reputation(id="daring", name="Daring"),
        Reputation(id="honorable", name="Honorable"),
        Reputation(id="professional", name="Professional"),
        Reputation(id="savvy", name="Savvy"),
        Reputation(id="subtle", name="Subtle"),
        Reputation(id="strange", name="Strange"),
    ]

def extract_tables():
    outcomes = [
        PositionRoll(
            position="controlled",
            results=[
                RollResult(level="critical", description="You do it with increased effect."),
                RollResult(level="6", description="You do it."),
                RollResult(level="4/5", description="You hesitate. Withdraw and try a different approach, or else do it with a minor consequence: a minor complication occurs, you have reduced effect, you suffer lesser harm, you end up in a risky position."),
                RollResult(level="1-3", description="You falter. Press on by seizing a risky opportunity, or withdraw and try a different approach.")
            ]
        ),
        PositionRoll(
            position="risky",
            results=[
                RollResult(level="critical", description="You do it with increased effect."),
                RollResult(level="6", description="You do it."),
                RollResult(level="4/5", description="You do it, but there's a consequence: you suffer harm, a complication occurs, you have reduced effect, you end up in a desperate position."),
                RollResult(level="1-3", description="Things go badly. You suffer harm, a complication occurs, you end up in a desperate position, you lose this opportunity.")
            ]
        ),
        PositionRoll(
            position="desperate",
            results=[
                RollResult(level="critical", description="You do it with increased effect."),
                RollResult(level="6", description="You do it."),
                RollResult(level="4/5", description="You do it, but there's a consequence: you suffer severe harm, a serious complication occurs, you have reduced effect."),
                RollResult(level="1-3", description="It's the worst outcome. You suffer severe harm, a serious complication occurs, you lose this opportunity for action.")
            ]
        )
    ]
    
    heat = [
        HeatPenalty(condition="0 heat", heat_added=0),
        HeatPenalty(condition="Smooth & quiet; low exposure", heat_added=0),
        HeatPenalty(condition="Contained; standard exposure", heat_added=2),
        HeatPenalty(condition="Loud & chaotic; high exposure", heat_added=4),
        HeatPenalty(condition="Wild; devastating exposure", heat_added=6),
        HeatPenalty(condition="High-profile or well-connected target", heat_added=1),
        HeatPenalty(condition="Situation happened on hostile turf", heat_added=1),
        HeatPenalty(condition="At war with another faction", heat_added=1),
        HeatPenalty(condition="Killing was involved", heat_added=2),
    ]

    entanglements = [
        EntanglementEntry(heat_band="0-3", roll_result="1-3", entanglement="Gang Trouble or The Usual Suspects"),
        EntanglementEntry(heat_band="0-3", roll_result="4/5", entanglement="Rivals or Unquiet Dead"),
        EntanglementEntry(heat_band="0-3", roll_result="6", entanglement="Cooperation"),
        EntanglementEntry(heat_band="4-5", roll_result="1-3", entanglement="Gang Trouble or Questioning"),
        EntanglementEntry(heat_band="4-5", roll_result="4/5", entanglement="Reprisals or Unquiet Dead"),
        EntanglementEntry(heat_band="4-5", roll_result="6", entanglement="Show of Force"),
        EntanglementEntry(heat_band="6", roll_result="1-3", entanglement="Flipped or Interrogation"),
        EntanglementEntry(heat_band="6", roll_result="4/5", entanglement="Demonic Notice or Show of Force"),
        EntanglementEntry(heat_band="6", roll_result="6", entanglement="Arrest"),
    ]
    
    return outcomes, heat, entanglements

def extract_items():
    return [
        Item(id="blade_or_two", name="A Blade or Two", load=1, description="A fighting knife, switchblade, or other small weapon."),
        Item(id="throwing_knives", name="Throwing Knives", load=1, description="Six small, balanced throwing blades."),
        Item(id="pistol", name="A Pistol", load=1, description="A heavy, single-shot pistol."),
        Item(id="large_weapon", name="A Large Weapon", load=2, description="A weapon requiring two hands (sword, pole-arm, rifle)."),
        Item(id="unusual_weapon", name="An Unusual Weapon", load=1, description="A whip, dart-thrower, trick-blade, etc."),
        Item(id="armor", name="Armor", load=2, description="Thick leather tunic and high boots."),
        Item(id="heavy_armor", name="Heavy Armor", load=3, description="Plate and chainmail (requires Armor)."),
        Item(id="burglary_gear", name="Burglary Gear", load=1, description="Lockpicks, prybar, wire-snippers, etc."),
        Item(id="climbing_gear", name="Climbing Gear", load=2, description="Rope, grappling hook, pitons."),
        Item(id="arcane_implements", name="Arcane Implements", load=1, description="Vials of blood, bone-dust, spirit-incense."),
        Item(id="documents", name="Documents", load=1, description="Forged papers, ledgers, blueprints."),
        Item(id="subterfuge_supplies", name="Subterfuge Supplies", load=1, description="Makeup, fake mustaches, disguises."),
        Item(id="demolition_tools", name="Demolition Tools", load=2, description="Sledgehammer, heavy prybar, etc."),
        Item(id="tinkering_tools", name="Tinkering Tools", load=1, description="Fine hand tools and supplies."),
        Item(id="lantern", name="Lantern", load=1, description="Oil or electroplasmic lamp.")
    ]

def extract_crew_upgrades():
    return [
        CrewUpgrade(id="boat_house", name="Boat House", description="A boat, a dock, and a shack.", cost=1),
        CrewUpgrade(id="carriage_house", name="Carriage House", description="A carriage, two draft animals, and a stable.", cost=1),
        CrewUpgrade(id="cohort", name="Cohort", description="A gang or expert NPC.", cost=2),
        CrewUpgrade(id="hidden_lair", name="Hidden Lair", description="Secret location.", cost=1),
        CrewUpgrade(id="mastery", name="Mastery", description="PC action ratings can reach 4.", cost=4),
        CrewUpgrade(id="quality", name="Quality", description="+1 quality for one gear type.", cost=1),
        CrewUpgrade(id="quarters", name="Quarters", description="Living space in lair.", cost=1),
        CrewUpgrade(id="secure_lair", name="Secure Lair", description="Locks, alarms, traps.", cost=1),
        CrewUpgrade(id="training", name="Training", description="2 xp instead of 1 when training a specific track.", cost=1),
        CrewUpgrade(id="vault", name="Vault", description="Secure storage for 8 coin.", cost=1),
        CrewUpgrade(id="workshop", name="Workshop", description="Tools for tinkering/alchemy.", cost=1)
    ]

def main():
    root_dir = Path(__file__).parent.parent
    srd_path = root_dir / "Blades-in-the-Dark-SRD.md"
    out_path = root_dir / "packs" / "srd_base.json"
    
    if not srd_path.exists():
        print(f"SRD file not found at {srd_path}")
        return
        
    srd_text = srd_path.read_text(encoding="utf-8")
    
    outcomes, heat, entanglements = extract_tables()
    
    pack = ContentPack(
        id="srd",
        name="Blades in the Dark SRD Base Pack",
        description="Core mechanics and abilities extracted from the SRD.",
        version="1.0.0",
        special_abilities=extract_special_abilities(srd_text),
        traumas=extract_traumas(),
        vices=extract_vices(),
        reputations=extract_reputations(),
        items=extract_items(),
        crew_upgrades=extract_crew_upgrades(),
        action_outcomes=outcomes,
        heat_penalties=heat,
        entanglements=entanglements
    )
    
    out_path.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote {len(pack.special_abilities)} abilities, {len(pack.items)} items, and tables to {out_path}")

if __name__ == "__main__":
    main()
