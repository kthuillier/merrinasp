%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% LP
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

reaction(R) :- r(_,_,R).
metabolite(M) :- r(_,M,_).

s(R,M,S) :- product(M,R,S), not out(M,R).
s(R,M,S) :- reactant(M,R,S), not inp(M,R).
s(R,M,"0") :- inp(M,R).
s(R,M,"0") :- out(M,R).
s(R,M,"0") :- reaction(R), metabolite(M), not product(M,R,_), not reactant(M,R,_).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% REGULATIONS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

&dom(w(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,U), not inp(_, R).
&dom(w(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,U), inp(M, R), obs(T,M,1), not restriction(T,R,_).
&dom(w(T)){L..S} = f(R):- debug(T), reaction(R), bounds(R,L,U), inp(M, R), obs(T,M,1), restriction(T,R,S).
&dom(w(T)){0..0} = f(R):- debug(T), reaction(R), inp(M, R), obs(T,M,-1).

&sum(w(T)){S * f(R): reaction(R), s(R,M,S)} = 0 :- debug(T), metabolite(M).

&sum(w(T)){f(R)} = 0 :- debug(T), reaction(R), node(R), w_obs(T, R, -1).

&assert(w(T)){f("Growth")} <= (("1.0" + K) * O) :- coeff(K), debug(T), obj(T, O).
&sum(w(T)){f("Growth")} >= (("1.0" - K) * O) :- coeff(K), debug(T), obj(T, O).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% STATES
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
&dom(v(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,U), not inp(_, R).
&dom(v(T)){L..U} = f(R):- debug(T), reaction(R), bounds(R,L,U), inp(M, R), obs(T,M,1).
&dom(v(T)){0..0} = f(R):- debug(T), reaction(R), inp(M, R), obs(T,M,-1).

&sum(v(T)){S * f(R): reaction(R), s(R,M,S)} = 0 :- debug(T), metabolite(M).

used_node(R) :- reaction(R), clause(_, _, R, _).
&sum(v(TO)){f(R)} = 0 :- debug(TO), reaction(R), tlink(TO, TM), used_node(R), v(TM, R, -1).
&sum(v(TO)){f(R)} >= E :- debug(TO), reaction(R), tlink(TO, TM),  used_node(R), v(TM, R, 1), epsilon(E).