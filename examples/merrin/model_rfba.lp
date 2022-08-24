%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% LP
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

upBound(T,R,U) :- debug(T), reaction(R), bounds(R,L,U), not inp(_, R).
upBound(T,R,U) :- debug(T), reaction(R), bounds(R,L,U), inp(M, R), obs(T,M,1), not restriction(T,R,_).
upBound(T,R,U) :- debug(T), reaction(R), inp(M, R), obs(T,M,1), restriction(T,R,U).
upBound(T,R,0) :- debug(T), reaction(R), inp(M, R), obs(T,M,-1).

reaction(R) :- r(_,_,R).
metabolite(M) :- r(_,M,_).

s(R,M,S) :- product(M,R,S), not out(M,R).
s(R,M,S) :- reactant(M,R,S), not inp(M,R).
s(R,M,"0") :- inp(M,R).
s(R,M,"0") :- out(M,R).
s(R,M,"0") :- reaction(R), metabolite(M), not product(M,R,_), not reactant(M,R,_).

gen_ref(T) :- debug(T), not dtype("Kinetics"), not dtype("Fluxomics").
unrestricted(T1,R) :- gen_ref(T1), next(T1,T2), inp(M,R), obs(T1,M,1), obs(T2,M,-1).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% REGULATIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

&dom(w(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,_), upBound(T,R,U).

&sum(w(T)){S * f(R): reaction(R), s(R,M,S)} = 0 :- debug(T), metabolite(M).

&sum(w(T)){f(R)} = 0 :- debug(T), reaction(R), node(R), w_obs(T, R, -1).

&assert(w(T)){f("Growth")} <= (("1.0" + K) * O) :- not gen_ref(T), coeff(K), debug(T), obj(T, O).
&sum(w(T)){f("Growth")} >= (("1.0" - K) * O) :- not gen_ref(T), coeff(K), debug(T), obj(T, O).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% REFERENCE GENERATION
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%%%%%%%%%%%
% VARIABLES
%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%
% PRIMAL
%%%%%%%%%%
&dom(w(T)){L..U} = r(R):- gen_ref(T), debug(T), reaction(R), bounds(R,L,U).

%%%%%%%%%%
% DUAL
%%%%%%%%%%
&dom(w(T)){ "0.0".."1.0"} = d(R) :- gen_ref(T), debug(T), reaction(R).
&dom(w(T)){"-1.0".."0.0"} = e(R) :- gen_ref(T), debug(T), reaction(R).
&dom(w(T)){"-1.0".."1.0"} = p(M) :- gen_ref(T), debug(T), metabolite(M).

%%%%%%%%%%%%%%%%%%%%
% OPTIMAL CONDITION
%%%%%%%%%%%%%%%%%%%%
&sum(w(T)){primal; -dual} = 0 :- gen_ref(T), debug(T).

%%%%%%%%%%%%%%%%%%%%
% rFBA - PRIMAL
%%%%%%%%%%%%%%%%%%%%
&sum(w(T)){primal; -r("Growth")} = 0 :- gen_ref(T), debug(T).
&sum(w(T)){S * r(R): reaction(R), s(R,M,S)} = 0 :- gen_ref(T), debug(T), metabolite(M).
&sum(w(T)){r(R)} >= E * S :- gen_ref(T), debug(T), reaction(R), obs(T,R,V), epsilon(E), S=(1+V)/2.
&sum(w(T)){r(R)} <= U * S :- gen_ref(T), debug(T), reaction(R), obs(T,R,V), upBound(T,R,U), S=(1+V)/2.

%%%%%%%%%%%%%%%%%%%%
% rFBA - DUAL
%%%%%%%%%%%%%%%%%%%%
&sum(w(T)){dual; -(U * S) * d(R): reaction(R), upBound(T,R,U), obs(T,R,V), S=(1+V)/2; -(E * S) * e(R): reaction(R), obs(T,R,V), epsilon(E), S=(1+V)/2} = 0 :- gen_ref(T), debug(T).
&sum(w(T)){d("Growth"); e("Growth"); S * p(M): metabolite(M), s("Growth",M,S), not inp(M,"Growth")} >= 1 :- gen_ref(T), debug(T), obs(T,"Growth",1).
&sum(w(T)){d(R); e(R); S * p(M): metabolite(M), s(R,M,S), not inp(M,R)} >= 0 :- gen_ref(T), debug(T), reaction(R), R!="Growth", obs(T,R,1).

%%%%%%%%%%%%%%%%%%%%
% REF Comparison
%%%%%%%%%%%%%%%%%%%%

&assert(w(T)){("1.0" + K) * r("Growth"); -f("Growth")} >= 0 :- gen_ref(T), coeff(K), debug(T).
&sum(w(T)){("1.0" - K) * r("Growth"); -f("Growth")} <= 0 :- gen_ref(T), coeff(K), debug(T).

%%%%%%%%%%%%%%%%%%%%
% REF Input Bounds
%%%%%%%%%%%%%%%%%%%%

&sum(w(T)){f(R); -r(R)} <= 0 :- gen_ref(T), debug(T), unrestricted(T,_), inp(_,R), obs(T,R,1).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% STATES
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
&dom(v(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,U), not inp(_, R).
&dom(v(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,U), inp(M, R), obs(T,M,1).
&dom(v(T)){0..0} = f(R):- debug(T), reaction(R), inp(M, R), obs(T,M,-1).

&sum(v(T)){S * f(R): reaction(R), s(R,M,S)} = 0 :- debug(T), metabolite(M).

used_node(R) :- reaction(R), clause(_, _, R, _).
&sum(v(TO)){f(R)} = 0 :- debug(TO), reaction(R), tlink(TO, TM), used_node(R), v(TM, R, -1).
&sum(v(TO)){f(R)} >= E :- debug(TO), reaction(R), tlink(TO, TM), used_node(R), v(TM, R, 1), epsilon(E).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% DEBUG
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Use to prevent warning
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
obj(-1, -1).
restriction(-1, -1, -1).